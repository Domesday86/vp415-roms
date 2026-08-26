#!/usr/bin/env python3
"""Disassemble the MCS-51 ROMs in this collection.

Module S (control), module R (drive processor) and the VP410 control ROM are
all 8031/8051 code in external ROM.  A linear disassembly is not much use:
these programs are built around `jmp @A+DPTR` tables, and the command
interpreter in module S is nothing but tables.  This tool does a recursive
descent from the reset and interrupt vectors, resolves the jump tables it
meets, and repeats until nothing new turns up.

Usage:
    vp-mcs51 IMAGE [-o DIR] [-e ADDR ...]
    vp-mcs51 IMAGE --tables

See docs/player-control-command-set.md for what module S's tables mean.
"""
import sys, os, argparse
from collections import defaultdict

SFR = {0x80:'P0',0x81:'SP',0x82:'DPL',0x83:'DPH',0x87:'PCON',0x88:'TCON',0x89:'TMOD',
       0x8A:'TL0',0x8B:'TL1',0x8C:'TH0',0x8D:'TH1',0x90:'P1',0x98:'SCON',0x99:'SBUF',
       0xA0:'P2',0xA8:'IE',0xB0:'P3',0xB8:'IP',0xD0:'PSW',0xE0:'ACC',0xF0:'B'}
BITSFR = {0x80:'P0',0x88:'TCON',0x90:'P1',0x98:'SCON',0xA0:'P2',0xA8:'IE',0xB0:'P3',
          0xB8:'IP',0xD0:'PSW',0xE0:'ACC',0xF0:'B'}

def d(a):
    if a in SFR: return SFR[a]
    if a >= 0x80: return '$%02X'%a
    return '%02Xh'%a

def bit(b):
    if b < 0x80:
        base = 0x20 + (b >> 3); return '%02Xh.%d'%(base, b & 7)
    base = b & 0xF8
    nm = BITSFR.get(base, '$%02X'%base)
    return '%s.%d'%(nm, b & 7)

def rel(pc, off): return (pc + (off - 256 if off > 127 else off)) & 0xFFFF

class Ins:
    __slots__ = ('addr','length','text','flow','targets','raw')
    def __init__(s,a,l,t,f,tg,raw): s.addr=a; s.length=l; s.text=t; s.flow=f; s.targets=tg; s.raw=raw

def decode(m, pc):
    op = m[pc]; hi = op & 0xF0; lo = op & 0x0F
    b1 = m[pc+1] if pc+1 < len(m) else 0
    b2 = m[pc+2] if pc+2 < len(m) else 0
    n = lambda ln, txt, flow='next', tg=(): Ins(pc, ln, txt, flow, list(tg), m[pc:pc+ln])
    if lo == 1 and (op & 0x0F) == 1:            # AJMP
        t = ((pc+2) & 0xF800) | ((op & 0xE0) << 3) | b1
        return n(2, 'ajmp  $%04X'%t, 'jump', [t])
    if lo == 1 and False: pass
    if op & 0x1F == 0x11:                       # ACALL
        t = ((pc+2) & 0xF800) | ((op & 0xE0) << 3) | b1
        return n(2, 'acall $%04X'%t, 'call', [t])
    if op & 0x1F == 0x01:                       # AJMP
        t = ((pc+2) & 0xF800) | ((op & 0xE0) << 3) | b1
        return n(2, 'ajmp  $%04X'%t, 'jump', [t])
    R = lambda: 'R%d'%(op & 7)
    Ri = lambda: '@R%d'%(op & 1)
    if op == 0x00: return n(1,'nop')
    if op == 0x02: t=(b1<<8)|b2; return n(3,'ljmp  $%04X'%t,'jump',[t])
    if op == 0x03: return n(1,'rr    A')
    if op == 0x04: return n(1,'inc   A')
    if op == 0x05: return n(2,'inc   %s'%d(b1))
    if op in (0x06,0x07): return n(1,'inc   %s'%Ri())
    if 0x08 <= op <= 0x0F: return n(1,'inc   %s'%R())
    if op == 0x10: t=rel(pc+3,b2); return n(3,'jbc   %s,$%04X'%(bit(b1),t),'cjump',[t])
    if op == 0x12: t=(b1<<8)|b2; return n(3,'lcall $%04X'%t,'call',[t])
    if op == 0x13: return n(1,'rrc   A')
    if op == 0x14: return n(1,'dec   A')
    if op == 0x15: return n(2,'dec   %s'%d(b1))
    if op in (0x16,0x17): return n(1,'dec   %s'%Ri())
    if 0x18 <= op <= 0x1F: return n(1,'dec   %s'%R())
    if op == 0x20: t=rel(pc+3,b2); return n(3,'jb    %s,$%04X'%(bit(b1),t),'cjump',[t])
    if op == 0x22: return n(1,'ret','ret')
    if op == 0x23: return n(1,'rl    A')
    if op == 0x24: return n(2,'add   A,#$%02X'%b1)
    if op == 0x25: return n(2,'add   A,%s'%d(b1))
    if op in (0x26,0x27): return n(1,'add   A,%s'%Ri())
    if 0x28 <= op <= 0x2F: return n(1,'add   A,%s'%R())
    if op == 0x30: t=rel(pc+3,b2); return n(3,'jnb   %s,$%04X'%(bit(b1),t),'cjump',[t])
    if op == 0x32: return n(1,'reti','ret')
    if op == 0x33: return n(1,'rlc   A')
    if op == 0x34: return n(2,'addc  A,#$%02X'%b1)
    if op == 0x35: return n(2,'addc  A,%s'%d(b1))
    if op in (0x36,0x37): return n(1,'addc  A,%s'%Ri())
    if 0x38 <= op <= 0x3F: return n(1,'addc  A,%s'%R())
    if op == 0x40: t=rel(pc+2,b1); return n(2,'jc    $%04X'%t,'cjump',[t])
    if op == 0x42: return n(2,'orl   %s,A'%d(b1))
    if op == 0x43: return n(3,'orl   %s,#$%02X'%(d(b1),b2))
    if op == 0x44: return n(2,'orl   A,#$%02X'%b1)
    if op == 0x45: return n(2,'orl   A,%s'%d(b1))
    if op in (0x46,0x47): return n(1,'orl   A,%s'%Ri())
    if 0x48 <= op <= 0x4F: return n(1,'orl   A,%s'%R())
    if op == 0x50: t=rel(pc+2,b1); return n(2,'jnc   $%04X'%t,'cjump',[t])
    if op == 0x52: return n(2,'anl   %s,A'%d(b1))
    if op == 0x53: return n(3,'anl   %s,#$%02X'%(d(b1),b2))
    if op == 0x54: return n(2,'anl   A,#$%02X'%b1)
    if op == 0x55: return n(2,'anl   A,%s'%d(b1))
    if op in (0x56,0x57): return n(1,'anl   A,%s'%Ri())
    if 0x58 <= op <= 0x5F: return n(1,'anl   A,%s'%R())
    if op == 0x60: t=rel(pc+2,b1); return n(2,'jz    $%04X'%t,'cjump',[t])
    if op == 0x62: return n(2,'xrl   %s,A'%d(b1))
    if op == 0x63: return n(3,'xrl   %s,#$%02X'%(d(b1),b2))
    if op == 0x64: return n(2,'xrl   A,#$%02X'%b1)
    if op == 0x65: return n(2,'xrl   A,%s'%d(b1))
    if op in (0x66,0x67): return n(1,'xrl   A,%s'%Ri())
    if 0x68 <= op <= 0x6F: return n(1,'xrl   A,%s'%R())
    if op == 0x70: t=rel(pc+2,b1); return n(2,'jnz   $%04X'%t,'cjump',[t])
    if op == 0x72: return n(2,'orl   C,%s'%bit(b1))
    if op == 0x73: return n(1,'jmp   @A+DPTR','ijump')
    if op == 0x74: return n(2,'mov   A,#$%02X'%b1)
    if op == 0x75: return n(3,'mov   %s,#$%02X'%(d(b1),b2))
    if op in (0x76,0x77): return n(2,'mov   %s,#$%02X'%(Ri(),b1))
    if 0x78 <= op <= 0x7F: return n(2,'mov   %s,#$%02X'%(R(),b1))
    if op == 0x80: t=rel(pc+2,b1); return n(2,'sjmp  $%04X'%t,'jump',[t])
    if op == 0x82: return n(2,'anl   C,%s'%bit(b1))
    if op == 0x83: return n(1,'movc  A,@A+PC')
    if op == 0x84: return n(1,'div   AB')
    if op == 0x85: return n(3,'mov   %s,%s'%(d(b2),d(b1)))
    if op in (0x86,0x87): return n(2,'mov   %s,%s'%(d(b1),Ri()))
    if 0x88 <= op <= 0x8F: return n(2,'mov   %s,%s'%(d(b1),R()))
    if op == 0x90: return n(3,'mov   DPTR,#$%04X'%((b1<<8)|b2))
    if op == 0x92: return n(2,'mov   %s,C'%bit(b1))
    if op == 0x93: return n(1,'movc  A,@A+DPTR')
    if op == 0x94: return n(2,'subb  A,#$%02X'%b1)
    if op == 0x95: return n(2,'subb  A,%s'%d(b1))
    if op in (0x96,0x97): return n(1,'subb  A,%s'%Ri())
    if 0x98 <= op <= 0x9F: return n(1,'subb  A,%s'%R())
    if op == 0xA0: return n(2,'orl   C,/%s'%bit(b1))
    if op == 0xA2: return n(2,'mov   C,%s'%bit(b1))
    if op == 0xA3: return n(1,'inc   DPTR')
    if op == 0xA4: return n(1,'mul   AB')
    if op == 0xA5: return n(1,'db    $A5')
    if op in (0xA6,0xA7): return n(2,'mov   %s,%s'%(Ri(),d(b1)))
    if 0xA8 <= op <= 0xAF: return n(2,'mov   %s,%s'%(R(),d(b1)))
    if op == 0xB0: return n(2,'anl   C,/%s'%bit(b1))
    if op == 0xB2: return n(2,'cpl   %s'%bit(b1))
    if op == 0xB3: return n(1,'cpl   C')
    if op == 0xB4: t=rel(pc+3,b2); return n(3,'cjne  A,#$%02X,$%04X'%(b1,t),'cjump',[t])
    if op == 0xB5: t=rel(pc+3,b2); return n(3,'cjne  A,%s,$%04X'%(d(b1),t),'cjump',[t])
    if op in (0xB6,0xB7): t=rel(pc+3,b2); return n(3,'cjne  %s,#$%02X,$%04X'%(Ri(),b1,t),'cjump',[t])
    if 0xB8 <= op <= 0xBF: t=rel(pc+3,b2); return n(3,'cjne  %s,#$%02X,$%04X'%(R(),b1,t),'cjump',[t])
    if op == 0xC0: return n(2,'push  %s'%d(b1))
    if op == 0xC2: return n(2,'clr   %s'%bit(b1))
    if op == 0xC3: return n(1,'clr   C')
    if op == 0xC4: return n(1,'swap  A')
    if op == 0xC5: return n(2,'xch   A,%s'%d(b1))
    if op in (0xC6,0xC7): return n(1,'xch   A,%s'%Ri())
    if 0xC8 <= op <= 0xCF: return n(1,'xch   A,%s'%R())
    if op == 0xD0: return n(2,'pop   %s'%d(b1))
    if op == 0xD2: return n(2,'setb  %s'%bit(b1))
    if op == 0xD3: return n(1,'setb  C')
    if op == 0xD4: return n(1,'da    A')
    if op == 0xD5: t=rel(pc+3,b2); return n(3,'djnz  %s,$%04X'%(d(b1),t),'cjump',[t])
    if op in (0xD6,0xD7): return n(1,'xchd  A,%s'%Ri())
    if 0xD8 <= op <= 0xDF: t=rel(pc+2,b1); return n(2,'djnz  %s,$%04X'%(R(),t),'cjump',[t])
    if op == 0xE0: return n(1,'movx  A,@DPTR')
    if op in (0xE2,0xE3): return n(1,'movx  A,%s'%Ri())
    if op == 0xE4: return n(1,'clr   A')
    if op == 0xE5: return n(2,'mov   A,%s'%d(b1))
    if op in (0xE6,0xE7): return n(1,'mov   A,%s'%Ri())
    if 0xE8 <= op <= 0xEF: return n(1,'mov   A,%s'%R())
    if op == 0xF0: return n(1,'movx  @DPTR,A')
    if op in (0xF2,0xF3): return n(1,'movx  %s,A'%Ri())
    if op == 0xF4: return n(1,'cpl   A')
    if op == 0xF5: return n(2,'mov   %s,A'%d(b1))
    if op in (0xF6,0xF7): return n(1,'mov   %s,A'%Ri())
    if 0xF8 <= op <= 0xFF: return n(1,'mov   %s,A'%R())
    return n(1,'db    $%02X'%op)

class Prog:
    def __init__(s, data):
        s.m = data
        s.insns = {}
        s.xrefs = defaultdict(set)
        s.callrefs = defaultdict(set)
        s.funcs = set()

    def trace(self, entries):
        work = list(entries)
        for e in entries: self.funcs.add(e)
        while work:
            pc = work.pop()
            while True:
                if pc in self.insns or pc >= len(self.m): break
                ins = decode(self.m, pc)
                self.insns[pc] = ins
                f = ins.flow
                if f in ('jump','cjump'):
                    for t in ins.targets:
                        self.xrefs[t].add(pc)
                        if t not in self.insns: work.append(t)
                    if f == 'jump': break
                elif f == 'call':
                    for t in ins.targets:
                        self.callrefs[t].add(pc); self.funcs.add(t)
                        if t not in self.insns: work.append(t)
                elif f in ('ret','ijump'): break
                pc += ins.length

    def listing(self, lo=0, hi=None, names=None):
        hi = len(self.m) if hi is None else hi
        names = names or {}
        out = []; a = lo
        while a < hi:
            if a in self.insns:
                if a in self.funcs or a in self.callrefs:
                    refs = sorted(self.callrefs.get(a, ()))
                    out.append('')
                    out.append('; ---- %s   callers: %s' % (
                        names.get(a, 'sub_%04X'%a),
                        ' '.join('%04X'%r for r in refs[:14]) or '-'))
                elif a in self.xrefs:
                    out.append('L%04X:  ; <- %s' % (a, ' '.join('%04X'%r for r in sorted(self.xrefs[a])[:14])))
                i = self.insns[a]
                out.append('%04X: %-9s %s' % (a, ' '.join('%02X'%b for b in i.raw), i.text))
                a += i.length
            else:
                st = a
                while a < hi and a not in self.insns: a += 1
                for r in range(st, a, 16):
                    ch = self.m[r:min(a, r+16)]
                    out.append('%04X: .db %-47s |%s|' % (r, ' '.join('%02X'%b for b in ch),
                               ''.join(chr(b) if 32 <= b < 127 else '.' for b in ch)))
        return '\n'.join(out)

# ---- jump-table resolution -------------------------------------------------
#
# Two idioms appear in this ROM:
#   mov DPTR,#tab / add A,ACC          / jmp @A+DPTR   -> 2-byte entries
#   mov DPTR,#tab / mov R0,A / add A,R0 / add A,R0 / jmp @A+DPTR -> 3-byte
# Entries are ljmp ($02) or ajmp/sjmp, so the table ends at the first byte
# that is not a jump opcode.

def find_table(m, insns, site):
    """Return (table address, entry size) for the jmp @A+DPTR at `site`."""
    prev = [a for a in sorted(insns) if a < site][-8:]
    tab = None; size = 2
    for a in prev:
        t = insns[a].text
        if t.startswith('mov   DPTR,#$'): tab = int(t.split('#$')[1], 16)
    body = ' '.join(insns[a].text for a in prev)
    if 'add   A,R0' in body: size = 3
    elif 'add   A,ACC' in body: size = 2
    return tab, size

def table_targets(m, tab, size, limit=256):
    out = []
    for i in range(limit):
        a = tab + size * i
        if a + size > len(m): break
        op = m[a]
        if size == 3:
            if op != 0x02: break
            out.append((m[a+1] << 8) | m[a+2])
        else:
            if op == 0x80:
                off = m[a+1]; out.append((a + 2 + (off - 256 if off > 127 else off)) & 0xFFFF)
            elif (op & 0x1F) == 0x01:
                out.append(((a + 2) & 0xF800) | ((op & 0xE0) << 3) | m[a+1])
            else:
                break
    return out

def trace_all(data, entries, max_rounds=40):
    """Trace, resolving jmp @A+DPTR tables, until nothing new appears."""
    p = Prog(data)
    p.trace(entries)
    tables = {}
    for _ in range(max_rounds):
        new = []
        for a, i in list(p.insns.items()):
            if i.flow != 'ijump' or a in tables: continue
            tab, size = find_table(data, p.insns, a)
            if tab is None: tables[a] = None; continue
            tgts = table_targets(data, tab, size)
            tables[a] = (tab, size, tgts)
            new.extend(t for t in tgts if t not in p.insns)
        if not new: break
        p.trace(new)
    p.tables = tables
    return p

# ---- vectors ---------------------------------------------------------------

VECTORS = [(0x0000,'reset'), (0x0003,'external interrupt 0'), (0x000B,'timer 0'),
           (0x0013,'external interrupt 1'), (0x001B,'timer 1'), (0x0023,'serial')]

def vector_entries(m):
    """Follow the ljmp at each MCS-51 vector that actually holds one."""
    out = []
    for a, name in VECTORS:
        if a + 2 < len(m) and m[a] == 0x02:
            out.append((((m[a+1] << 8) | m[a+2]), name))
    return out

def main():
    ap = argparse.ArgumentParser(description='Disassemble an MCS-51 ROM image.')
    ap.add_argument('image')
    ap.add_argument('-o', '--out', default='disasm', help='output directory')
    ap.add_argument('-e', '--entry', action='append', default=[],
                    help='extra entry point, hex (repeatable)')
    ap.add_argument('-t', '--tables', action='store_true',
                    help='list the jump tables found and exit')
    args = ap.parse_args()

    m = open(args.image, 'rb').read()
    ents = [a for a, _ in vector_entries(m)] + [int(e, 16) for e in args.entry]
    if not ents:
        raise SystemExit('no ljmp at any interrupt vector -- is this MCS-51 code?')
    p = trace_all(m, ents)

    prog = sum(1 for b in m if b != 0xFF)
    cov = sum(i.length for i in p.insns.values())
    for a, name in vector_entries(m):
        print('  vector %-22s -> $%04X' % (name, a))
    print('instructions   %d' % len(p.insns))
    print('bytes decoded  %d of %d programmed (%.1f%%)' % (cov, prog, 100.0 * cov / prog))
    tabs = sum(1 for v in p.tables.values() if v)
    print('jump tables    %d resolved, %d unresolved'
          % (tabs, len(p.tables) - tabs))
    if args.tables:
        for site, v in sorted(p.tables.items()):
            if v: print('  $%04X -> table $%04X, %d-byte entries, %d entries'
                        % (site, v[0], v[1], len(v[2])))
            else: print('  $%04X -> UNRESOLVED' % site)
        return

    os.makedirs(args.out, exist_ok=True)
    base = os.path.join(args.out,
                        os.path.splitext(os.path.basename(args.image))[0])
    with open(base + '.lst', 'w') as f:
        f.write(p.listing() + '\n')
    print('wrote %s.lst' % base)

if __name__ == '__main__':
    main()
