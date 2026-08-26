#!/usr/bin/env python3
"""Disassemble the Philips VP415 module W LV-DOS firmware.

Module W's Z80 does not run LV-DOS as native code.  LVDOS#1 holds a
byte-code interpreter, LVDOS#2 holds its 160-entry opcode dispatch
table, and the application itself is byte code scattered through both
EPROMs.  A linear Z80 disassembly of these images is therefore mostly
nonsense.  This tool finds the interpreter, decodes the byte code, and
separately disassembles the native hardware primitives.

Usage:
    vp-lvdos LVDOS1.bin LVDOS2.bin [-o DIR]
    vp-lvdos LVDOS1.bin LVDOS2.bin --map

See docs/module-w-command-interface.md for what the output means.
"""
import sys, os, argparse
from collections import defaultdict

R8  = ['b','c','d','e','h','l','(hl)','a']
RP  = ['bc','de','hl','sp']
RP2 = ['bc','de','hl','af']
CC  = ['nz','z','nc','c','po','pe','p','m']
ALU = ['add a,','adc a,','sub ','sbc a,','and ','xor ','or ','cp ']
ROT = ['rlc','rrc','rl','rr','sla','sra','sll','srl']
IM  = ['0','0/1','1','2','0','0/1','1','2']

class Insn:
    __slots__=('addr','length','text','flow','targets','raw')
    def __init__(s,addr,length,text,flow,targets,raw):
        s.addr=addr; s.length=length; s.text=text; s.flow=flow; s.targets=targets; s.raw=raw

def d8(m,a):  return m[a]
def s8(m,a):  v=m[a]; return v-256 if v>127 else v
def d16(m,a): return m[a] | (m[a+1]<<8)

def hx(v,n=2): return ('$%0'+str(n)+'X')%v

def decode(m, pc, base=0):
    """Return Insn. flow in {'next','jump','cjump','call','ccall','ret','cret','rst','stop','ijump'}"""
    start = pc
    idx = pc - base
    op = m[idx]
    tgt = []
    flow = 'next'
    # prefixes
    if op in (0xDD,0xFD):
        ix = 'ix' if op==0xDD else 'iy'
        ixh,ixl = (ix+'h'), (ix+'l')
        op2 = m[idx+1]
        if op2 == 0xCB:
            disp = s8(m, idx+2); sub = m[idx+3]
            y = (sub>>3)&7; z = sub&7
            ind = "(%s%+d)"%(ix,disp)
            if (sub>>6)==0: txt = "%s %s"%(ROT[y], ind)
            elif (sub>>6)==1: txt = "bit %d,%s"%(y,ind)
            elif (sub>>6)==2: txt = "res %d,%s"%(y,ind)
            else: txt = "set %d,%s"%(y,ind)
            return Insn(start,4,txt,'next',[],m[idx:idx+4])
        # substitute hl->ix in the base decode
        sub = decode_base(m, idx+1, base, ix=ix)
        ln = sub[1]+1
        txt = sub[0]
        return Insn(start, ln, txt, sub[2], [t+0 for t in sub[3]], m[idx:idx+ln])
    if op == 0xCB:
        sub = m[idx+1]; y=(sub>>3)&7; z=sub&7
        if (sub>>6)==0: txt = "%s %s"%(ROT[y],R8[z])
        elif (sub>>6)==1: txt = "bit %d,%s"%(y,R8[z])
        elif (sub>>6)==2: txt = "res %d,%s"%(y,R8[z])
        else: txt = "set %d,%s"%(y,R8[z])
        return Insn(start,2,txt,'next',[],m[idx:idx+2])
    if op == 0xED:
        sub = m[idx+2-1]
        sub = m[idx+1]
        x=(sub>>6)&3; y=(sub>>3)&7; z=sub&7; p=y>>1; q=y&1
        if x==1:
            if z==0: txt = "in %s,(c)"%(R8[y] if y!=6 else 'f'); return Insn(start,2,txt,'next',[],m[idx:idx+2])
            if z==1: txt = "out (c),%s"%(R8[y] if y!=6 else '0'); return Insn(start,2,txt,'next',[],m[idx:idx+2])
            if z==2: txt = ("sbc hl,%s" if q==0 else "adc hl,%s")%RP[p]; return Insn(start,2,txt,'next',[],m[idx:idx+2])
            if z==3:
                nn=d16(m,idx+2)
                txt = ("ld (%s),%s"%(hx(nn,4),RP[p])) if q==0 else ("ld %s,(%s)"%(RP[p],hx(nn,4)))
                return Insn(start,4,txt,'next',[],m[idx:idx+4])
            if z==4: return Insn(start,2,"neg",'next',[],m[idx:idx+2])
            if z==5:
                txt = "retn" if y!=1 else "reti"
                return Insn(start,2,txt,'ret',[],m[idx:idx+2])
            if z==6: return Insn(start,2,"im %s"%IM[y],'next',[],m[idx:idx+2])
            if z==7:
                t=['ld i,a','ld r,a','ld a,i','ld a,r','rrd','rld','nop','nop'][y]
                return Insn(start,2,t,'next',[],m[idx:idx+2])
        if x==2 and z<4 and y>=4:
            names={(4,0):'ldi',(4,1):'cpi',(4,2):'ini',(4,3):'outi',
                   (5,0):'ldd',(5,1):'cpd',(5,2):'ind',(5,3):'outd',
                   (6,0):'ldir',(6,1):'cpir',(6,2):'inir',(6,3):'otir',
                   (7,0):'lddr',(7,1):'cpdr',(7,2):'indr',(7,3):'otdr'}
            return Insn(start,2,names[(y,z)],'next',[],m[idx:idx+2])
        return Insn(start,2,"db $ED,%s"%hx(sub),'next',[],m[idx:idx+2])
    r = decode_base(m, idx, base)
    return Insn(start, r[1], r[0], r[2], r[3], m[idx:idx+r[1]])

def decode_base(m, idx, base, ix=None):
    """returns (text, length, flow, targets)"""
    def rr(i):
        if ix is None: return R8[i]
        if i==4: return ix+'h'
        if i==5: return ix+'l'
        return R8[i]
    def hl():
        return ix if ix else 'hl'
    op = m[idx]
    x=(op>>6)&3; y=(op>>3)&7; z=op&7; p=y>>1; q=y&1
    ilen_extra = 0
    def ind(off_idx):
        # (ix+d)
        return "(%s%+d)"%(ix, s8(m,off_idx))
    if x==0:
        if z==0:
            if y==0: return ("nop",1,'next',[])
            if y==1: return ("ex af,af'",1,'next',[])
            if y==2:
                t = base+idx+2+s8(m,idx+1); return ("djnz %s"%hx(t,4),2,'cjump',[t])
            if y==3:
                t = base+idx+2+s8(m,idx+1); return ("jr %s"%hx(t,4),2,'jump',[t])
            t = base+idx+2+s8(m,idx+1); return ("jr %s,%s"%(CC[y-4],hx(t,4)),2,'cjump',[t])
        if z==1:
            if q==0:
                nn=d16(m,idx+1)
                nm = hl() if p==2 else RP[p]
                return ("ld %s,%s"%(nm,hx(nn,4)),3,'next',[])
            nm = hl() if p==2 else RP[p]
            return ("add %s,%s"%(hl(),nm),1,'next',[])
        if z==2:
            if q==0:
                if p==0: return ("ld (bc),a",1,'next',[])
                if p==1: return ("ld (de),a",1,'next',[])
                if p==2: return ("ld (%s),%s"%(hx(d16(m,idx+1),4),hl()),3,'next',[])
                return ("ld (%s),a"%hx(d16(m,idx+1),4),3,'next',[])
            else:
                if p==0: return ("ld a,(bc)",1,'next',[])
                if p==1: return ("ld a,(de)",1,'next',[])
                if p==2: return ("ld %s,(%s)"%(hl(),hx(d16(m,idx+1),4)),3,'next',[])
                return ("ld a,(%s)"%hx(d16(m,idx+1),4),3,'next',[])
        if z==3:
            nm = hl() if p==2 else RP[p]
            return (("inc %s" if q==0 else "dec %s")%nm,1,'next',[])
        if z==4 or z==5:
            mn = "inc" if z==4 else "dec"
            if y==6 and ix: return ("%s %s"%(mn,ind(idx+1)),2,'next',[])
            return ("%s %s"%(mn,rr(y)),1,'next',[])
        if z==6:
            if y==6 and ix: return ("ld %s,%s"%(ind(idx+1),hx(m[idx+2])),3,'next',[])
            return ("ld %s,%s"%(rr(y),hx(m[idx+1])),2,'next',[])
        return (['rlca','rrca','rla','rra','daa','cpl','scf','ccf'][y],1,'next',[])
    if x==1:
        if y==6 and z==6: return ("halt",1,'stop',[])
        if ix and (y==6 or z==6):
            if y==6: return ("ld %s,%s"%(ind(idx+1),R8[z]),2,'next',[])
            return ("ld %s,%s"%(R8[y],ind(idx+1)),2,'next',[])
        return ("ld %s,%s"%(rr(y),rr(z)),1,'next',[])
    if x==2:
        if ix and z==6: return ("%s%s"%(ALU[y],ind(idx+1)),2,'next',[])
        return ("%s%s"%(ALU[y],rr(z)),1,'next',[])
    # x==3
    if z==0: return ("ret %s"%CC[y],1,'cret',[])
    if z==1:
        if q==0:
            nm = hl() if p==3 else RP2[p]
            if p==3: nm='af'
            return ("pop %s"%(hl() if p==2 else RP2[p]),1,'next',[])
        if p==0: return ("ret",1,'ret',[])
        if p==1: return ("exx",1,'next',[])
        if p==2: return ("jp (%s)"%hl(),1,'ijump',[])
        return ("ld sp,%s"%hl(),1,'next',[])
    if z==2:
        nn=d16(m,idx+1); return ("jp %s,%s"%(CC[y],hx(nn,4)),3,'cjump',[nn])
    if z==3:
        if y==0: nn=d16(m,idx+1); return ("jp %s"%hx(nn,4),3,'jump',[nn])
        if y==1: return ("db $CB",1,'next',[])
        if y==2: return ("out (%s),a"%hx(m[idx+1]),2,'next',[])
        if y==3: return ("in a,(%s)"%hx(m[idx+1]),2,'next',[])
        if y==4: return ("ex (sp),%s"%hl(),1,'next',[])
        if y==5: return ("ex de,hl",1,'next',[])
        if y==6: return ("di",1,'next',[])
        return ("ei",1,'next',[])
    if z==4:
        nn=d16(m,idx+1); return ("call %s,%s"%(CC[y],hx(nn,4)),3,'ccall',[nn])
    if z==5:
        if q==0: return ("push %s"%(hl() if p==2 else RP2[p]),1,'next',[])
        if p==0: nn=d16(m,idx+1); return ("call %s"%hx(nn,4),3,'call',[nn])
        return ("db",1,'next',[])
    if z==6:
        return ("%s%s"%(ALU[y],hx(m[idx+1])),2,'next',[])
    return ("rst %s"%hx(y*8),1,'rst',[y*8])

# ---------------- tracer ----------------
class Prog:
    def __init__(self, data, base=0, ram_start=0x8000):
        self.m = data; self.base=base; self.end=base+len(data)
        self.ram_start=ram_start
        self.insns = {}       # addr -> Insn
        self.xrefs = defaultdict(set)   # target -> set(from)
        self.callrefs = defaultdict(set)
        self.datarefs = defaultdict(set)
        self.funcs = set()
        self.labels = {}

    def inrom(self,a): return self.base <= a < self.end

    def trace(self, entries, stop_at_ret=True, maxdepth=200000):
        work = list(entries)
        for e in entries: self.funcs.add(e)
        seen=set()
        while work:
            pc = work.pop()
            while True:
                if pc in self.insns or not self.inrom(pc): break
                if pc+4 > self.end: break
                try: ins = decode(self.m, pc, self.base)
                except Exception: break
                self.insns[pc]=ins
                f=ins.flow
                if f in ('jump','cjump'):
                    for t in ins.targets:
                        self.xrefs[t].add(pc)
                        if self.inrom(t) and t not in self.insns: work.append(t)
                    if f=='jump': break
                elif f in ('call','ccall'):
                    for t in ins.targets:
                        self.callrefs[t].add(pc); self.funcs.add(t)
                        if self.inrom(t) and t not in self.insns: work.append(t)
                elif f=='rst':
                    for t in ins.targets:
                        self.callrefs[t].add(pc); self.funcs.add(t)
                        if self.inrom(t) and t not in self.insns: work.append(t)
                elif f in ('ret','stop','ijump'):
                    break
                pc += ins.length

    def listing(self, lo=None, hi=None, show_data=True):
        lo = self.base if lo is None else lo
        hi = self.end if hi is None else hi
        out=[]
        a=lo
        while a < hi:
            if a in self.insns:
                ins=self.insns[a]
                pre=''
                if a in self.callrefs or a in self.funcs:
                    refs=sorted(self.callrefs.get(a,()))
                    out.append('')
                    out.append('; ---- sub_%04X   callers: %s'%(a, ' '.join('%04X'%r for r in refs[:12]) or '-'))
                elif a in self.xrefs:
                    refs=sorted(self.xrefs[a])
                    out.append('L%04X:   ; from %s'%(a,' '.join('%04X'%r for r in refs[:12])))
                raw=' '.join('%02x'%b for b in ins.raw)
                out.append('%04X: %-12s %s'%(a,raw,ins.text))
                a+=ins.length
            else:
                # gather run of data
                st=a
                while a<hi and a not in self.insns: a+=1
                if show_data:
                    for r in range(st,a,16):
                        chunk=self.m[r-self.base:min(a,r+16)-self.base]
                        hexs=' '.join('%02x'%b for b in chunk)
                        asc=''.join(chr(b) if 32<=b<127 else '.' for b in chunk)
                        mark = ' <<' if r in self.xrefs or r in self.datarefs else ''
                        out.append('%04X: .db %-47s |%s|%s'%(r,hexs,asc,mark))
        return '\n'.join(out)

# =====================================================================
#  LV-DOS p-code layer
# =====================================================================
#
# Module W's CPU does not run the LV-DOS application as native Z80.  It
# runs a byte-coded stack machine whose interpreter lives in LVDOS#1 and
# whose 160-entry opcode dispatch table lives in LVDOS#2.  Everything
# below decodes that byte code.  See docs/module-w-lvdos-vm.md.

class Cur:
    def __init__(s, m, a): s.m = m; s.a = a
    def u8(s):  v = s.m[s.a]; s.a += 1; return v
    def u16(s): v = s.m[s.a] | (s.m[s.a + 1] << 8); s.a += 2; return v

def varint(c):
    """sub_2E29: a byte < $80 is the value; otherwise (a & $7F) << 8 | next."""
    a = c.u8()
    return a if a < 0x80 else (((a & 0x7f) << 8) | c.u8())

def mbf(b):
    """Microsoft Binary Format, 4 bytes, exponent bias $81."""
    if b[0] == 0: return 0.0
    sign = -1 if b[1] & 0x80 else 1
    mant = 1.0 + ((((b[1] & 0x7f) << 16) | (b[2] << 8) | b[3]) / 2 ** 23)
    return sign * mant * 2 ** (b[0] - 0x81)

def addr(c):
    """sub_2E54 -- the variable-length effective-address descriptor."""
    m0 = c.u8()
    if m0 == 0x02: return "abs $%04X" % c.u16()
    if m0 == 0x82: return "fp+$%04X" % c.u16()
    if m0 == 0x81: return "fp+$%02X" % c.u8()
    parts = []
    base = m0 & 0xC0
    if base in (0x80, 0xC0): parts.append("fp")
    elif base == 0x40:       parts.append("frame(lvl %d)" % c.u8())
    else:                    parts.append("0")
    ind = m0 & 0x0C
    if ind:
        off = 0 if ind == 0x04 else (c.u8() if ind == 0x08 else c.u16())
        parts.append("[+$%X]->" % off)
    d = m0 & 0x03
    if d == 1:   parts.append("+$%02X" % c.u8())
    elif d >= 2: parts.append("+$%04X" % c.u16())
    if m0 & 0x30: parts.append("+stkidx")
    if d == 1 and not (m0 & 0x30): parts.append("*sc$%02X" % c.u8())
    return "[" + " ".join(parts) + " mode$%02X]" % m0

TAB = {}
def deco(op, name, fn): TAB[op] = (name, fn)

def f_none(c): return ""
def f_u8(c):   return "$%02X" % c.u8()
def f_u16(c):  return "$%04X" % c.u16()
def f_addr(c): return addr(c)
def f_var(c):  return "n=%d" % varint(c)
def f_1addr(c):
    b = c.u8(); return "$%02X, %s" % (b, addr(c))

def _build():
    for i in range(0x10): deco(i, "PUSHC%d" % i, f_none)
    deco(0x11, "DIV", f_none);      deco(0x12, "DIV.r", f_none)
    deco(0x13, "ARGW", f_none)
    deco(0x15, "SCMP.EQ", f_var);   deco(0x16, "CMP.EQ", f_none)
    deco(0x17, "ARGSPC", f_none);   deco(0x18, "ARGSPC2", f_none)
    deco(0x19, "PUSHPROC", lambda c: "lvl %d, $%04X" % (c.u8(), c.u16()))
    deco(0x1A, "SCMP.GE", f_var);   deco(0x1B, "CMP.GE", f_none)
    deco(0x1C, "ARG3", f_none)
    deco(0x1D, "SCMP.GT", f_var);   deco(0x1E, "CMP.GT", f_none)
    deco(0x1F, "IDXC2", f_u16)
    deco(0x20, "IDXC3", lambda c: "$%04X,$%02X" % (c.u16(), c.u8()))
    deco(0x23, "IDX.SCALE", f_var); deco(0x24, "IDX.ADD", f_var)
    deco(0x25, "IDX.DESC", f_addr); deco(0x27, "IDX.DESC2", f_addr)
    deco(0x26, "BITADDR", f_u8);    deco(0x2A, "BITADDR2", f_u8)
    deco(0x2D, "ARGW2", f_none)
    deco(0x2E, "LDB", f_addr);      deco(0x2F, "PUSHB", f_u8)
    deco(0x30, "LDW", f_addr);      deco(0x31, "PUSHW", f_u16)
    deco(0x32, "LEA", f_addr);      deco(0x34, "LDIND", f_none)
    deco(0x35, "BITGET", f_1addr);  deco(0x54, "BITSET", f_1addr)
    deco(0x36, "SCMP.LE", f_var);   deco(0x37, "CMP.LE", f_none)
    deco(0x38, "SCMP.LT", f_var);   deco(0x39, "CMP.LT", f_none)
    deco(0x3A, "LDF", f_addr)
    deco(0x3C, "MUL", f_none)
    deco(0x3D, "MOD", f_none);      deco(0x3E, "MOD.r", f_none)
    deco(0x3F, "BLKMOV", f_var);    deco(0x40, "BLKMOV.r", f_var)
    deco(0x41, "NEG", f_none)
    deco(0x42, "SCMP.NE", f_var);   deco(0x43, "CMP.NE", f_none)
    deco(0x44, "DROP", f_none);     deco(0x4A, "DROP2", f_none)
    deco(0x49, "DROP.j", f_none)
    deco(0x45, "NOT", f_none);      deco(0x46, "NOTB", f_none)
    deco(0x47, "OR", f_none);       deco(0x60, "AND", f_none)
    deco(0x48, "RET.1", f_none);    deco(0x4B, "RET.FF", f_none)
    deco(0x4D, "RET.0", f_none)
    deco(0x4C, "DEC", f_none);      deco(0x57, "INC", f_none)
    deco(0x4E, "SUB", f_none);      deco(0x4F, "SUB.r", f_none)
    deco(0x5F, "ADD", f_none);      deco(0x50, "SQR", f_none)
    deco(0x51, "STB", f_addr);      deco(0x52, "STW", f_addr)
    deco(0x53, "STW.d", f_addr);    deco(0x56, "STF", f_addr)
    deco(0x55, "HALT", f_none);     deco(0x5A, "ARGF", f_addr)
    deco(0x58, "SWAP3", f_none);    deco(0x59, "SWAP3b", f_none)
    deco(0x5D, "ROT3", f_none)
    deco(0x5B, "MAXSWAP", f_none);  deco(0x5C, "MINSWAP", f_none)
    deco(0x5E, "ABS", f_none);      deco(0x63, "CALLIND", f_addr)
    for op, nm in ((0x65,"LDB"),(0x68,"LDW"),(0x6B,"LDF"),(0x6E,"LEA"),
                   (0x71,"STB"),(0x74,"STW"),(0x77,"STF")):
        deco(op,     nm + ".A", None)
        deco(op + 1, nm + ".b", None)
        deco(op + 2, nm + ".W", None)
    FP = ['F.ABS','F.ADD','F.DIV','F.DIV.r','F.EQ','F.ITOF2','F.ITOF','F.GE','F.GT',
          'F.LE','F.LT','F.MUL','F.NEG','F.NE','F.ROUND','F.SQR','F.SUB','F.SUB.r',
          'F.TRUNC','F.ITOF3','F.ESC']
    for i, n in enumerate(FP): deco(0x80 + i, n, f_none)
    deco(0x96, "RCHK.B",    lambda c: "lo $%02X hi $%02X" % (c.u8(), c.u8()))
    deco(0x97, "RCHK.W",    lambda c: "lo $%04X hi $%04X" % (c.u16(), c.u16()))
    deco(0x98, "RCHK.M",    f_addr)
    deco(0x99, "RCHK.B2",   lambda c: "lo $%02X hi $%02X" % (c.u8(), c.u8()))
    deco(0x9A, "RCHK.M2",   f_addr)
    deco(0x9B, "RCHK.HI.B", f_u8);  deco(0x9C, "RCHK.HI.W", f_u16)
    deco(0x9D, "RCHK.LO.B", f_u8);  deco(0x9E, "RCHK.LO.W", f_u16)
    deco(0x9F, "RCHK.2",    lambda c: "lo $%02X hi $%02X" % (c.u8(), c.u8()))
_build()

QUICK = {}
for _op in (0x65,0x68,0x6B,0x6E,0x71,0x74,0x77):
    QUICK[_op] = 'A'; QUICK[_op + 1] = 'b'; QUICK[_op + 2] = 'W'
EXT = {0:'SETASSIGN', 1:'SETASSIGN1', 2:'STRIDX', 3:'BLKASSIGN', 4:'BLKASSIGN1'}

def decode_vm(m, pc):
    """-> (length, mnemonic, operand text, flow, targets)"""
    c = Cur(m, pc); op = c.u8()
    if op in QUICK:
        mode = QUICK[op]
        o = ("abs $%04X" % c.u16()) if mode == 'A' else \
            ("fp+$%02X" % c.u8())   if mode == 'b' else \
            ("fp+$%04X" % c.u16())
        return c.a - pc, TAB[op][0], o, 'next', []
    if op == 0x2B: t = c.u16(); return c.a - pc, "JMP", "$%04X" % t, 'jump',  [t]
    if op == 0x2C: t = c.u16(); return c.a - pc, "JZ",  "$%04X" % t, 'cjump', [t]
    if op == 0x61:
        v = c.u8();  t = c.u16(); return c.a-pc, "CASEB", "$%02X -> $%04X" % (v,t), 'cjump', [t]
    if op == 0x62:
        v = c.u16(); t = c.u16(); return c.a-pc, "CASEW", "$%04X -> $%04X" % (v,t), 'cjump', [t]
    if op in (0x10, 0x21, 0x7A, 0x7B):
        a = addr(c); t = c.u16()
        nm = {0x10:"DECW.JNZ", 0x21:"INCW.JNZ", 0x7A:"INCB.JNZ", 0x7B:"DECB.JNZ"}[op]
        return c.a - pc, nm, "%s, $%04X" % (a, t), 'cjump', [t]
    if op == 0x64:
        lvl = c.u8(); t = c.u16()
        return c.a - pc, "CALL", "lvl %d, $%04X" % (lvl, t), 'call', [t]
    if op == 0x28:
        lo = c.u8(); hi = c.u8(); ts = [c.u16() for _ in range(hi - lo + 1)]
        return c.a-pc, "CASETAB", "lo $%02X hi $%02X : " % (lo,hi) + \
               ' '.join('$%04X' % t for t in ts), 'jumptab', ts
    if op == 0x29:
        lo = c.u16(); hi = c.u16(); ts = [c.u16() for _ in range(min(hi - lo + 1, 512))]
        return c.a-pc, "CASETABW", "lo $%04X hi $%04X : " % (lo,hi) + \
               ' '.join('$%04X' % t for t in ts), 'jumptab', ts
    if op == 0x33:
        n = varint(c); data = m[c.a:c.a + n]; c.a += n
        asc = ''.join(chr(b) if 32 <= b < 127 else '.' for b in data)
        return c.a-pc, "LITBLK", "n=%d |%s| %s" % (n, asc,
               ' '.join('%02X' % b for b in data[:24])), 'next', []
    if op == 0x3B:
        b = [m[pc+1], m[pc+2], m[pc+3], m[pc+4]]
        return 5, "PUSHF", "%s  ; %g" % (' '.join('%02X' % x for x in b), mbf(b)), 'next', []
    if op == 0x7F:
        sub = c.u8(); o = addr(c)
        return c.a - pc, "EXT.%s" % EXT.get(sub, '%02X' % sub), o, 'next', []
    if op in (0x48, 0x4B, 0x4D, 0x55):
        return 1, TAB[op][0], "", 'ret', []
    if op not in TAB:
        return 1, "db", "$%02X" % op, 'bad', []
    name, f = TAB[op]
    o = f(c) if f else ""          # must run before c.a is read
    return c.a - pc, name, o, 'next', []


# =====================================================================
#  Whole-image analysis
# =====================================================================

class LvDos:
    """Recursive-descent trace of an LV-DOS image (LVDOS#1 ++ LVDOS#2)."""

    def __init__(self, data):
        self.M = data
        # locate the interpreter, the p-code entry point and the prologue,
        # so the same code works on both 1.3 and 1.4 without a table.
        import re
        m = re.search(rb'\x4e\x06\x00\x23\x22(..)\xeb\x21(..)\x09\x09\x7e\x23\x66\x6f\xe9', data)
        if not m: raise SystemExit('no p-code interpreter found -- not an LV-DOS image?')
        self.fetch     = m.start()
        self.ip_var    = m.group(1)[0] | m.group(1)[1] << 8
        self.disp_tab  = m.group(2)[0] | m.group(2)[1] << 8
        m = re.search(rb'\xe1\x23\x4e\x23\x46\x23\xeb\x2a', data)
        self.prologue  = m.start()
        self.sig       = bytes([0xCD, self.prologue & 0xFF, self.prologue >> 8])
        m = re.search(rb'\x21(..)\xc3' + bytes([self.fetch & 0xFF, self.fetch >> 8]), data)
        self.entry     = m.group(1)[0] | m.group(1)[1] << 8
        m = re.search(rb'\xc5\xe5\x37\x3f\x06\x00\xcb\x11\xcb\x10\xcb\x11\xcb\x10\x21(..)', data)
        self.gateway   = m.start()
        self.hw_tab    = m.group(1)[0] | m.group(1)[1] << 8
        self.vm        = {}
        self.xref      = {}
        self.proc      = {}
        self.callers   = {}

    def hw_prims(self):
        """The native hardware primitives, indexed by selector."""
        out = []
        i = self.hw_tab
        while self.M[i] == 0xC3 and i < self.hw_tab + 44 * 4:
            out.append(self.M[i+1] | (self.M[i+2] << 8)); i += 4
        return out

    def trace(self):
        work = [self.entry]
        self.proc[self.entry] = 'entry'
        pending = [self.entry]
        while pending:
            t = pending.pop()
            body = t
            if t != self.entry:
                c = Cur(self.M, t + 3)
                c.u8(); frame = c.u16(); extra = varint(c); c.a += 2
                self.proc[t] = ('vm', frame, extra, c.a); body = c.a
            self._walk(body, pending)

    def _walk(self, start, pending):
        stack = [start]
        while stack:
            pc = stack.pop()
            while True:
                if pc in self.vm or pc >= len(self.M): break
                try: r = decode_vm(self.M, pc)
                except Exception: break
                ln, mn, o, flow, tg = r
                if not ln: break
                self.vm[pc] = r
                if flow == 'call':
                    t = tg[0]
                    self.callers.setdefault(t, set()).add(pc)
                    if t not in self.proc:
                        if self.M[t:t+3] == self.sig:
                            self.proc[t] = 'pending'; pending.append(t)
                        else:
                            self.proc[t] = 'native'
                elif flow in ('jump', 'cjump', 'jumptab'):
                    for t in tg:
                        self.xref.setdefault(t, set()).add(pc)
                        if t and t < len(self.M) and t not in self.vm: stack.append(t)
                    if flow == 'jump': break
                elif flow in ('ret', 'bad'): break
                pc += ln

    def listing(self):
        out = []
        starts = {v[3]: (t, v) for t, v in self.proc.items() if isinstance(v, tuple)}
        addrs = sorted(self.vm); a = addrs[0]; hi = addrs[-1]
        while a <= hi:
            if a in self.vm:
                if a in starts:
                    t, v = starts[a]
                    cs = sorted(self.callers.get(t, ()))
                    out.append('')
                    out.append('; ==== PROC_%04X   frame=%d locals=%d   callers: %s'
                               % (t, (v[1] - 65536 if v[1] > 32767 else v[1]), v[2],
                                  ' '.join('%04X' % c for c in cs) or '-'))
                elif a in self.xref:
                    out.append('L%04X:  ; <- %s'
                               % (a, ' '.join('%04X' % s for s in sorted(self.xref[a]))))
                ln, mn, o, fl, tg = self.vm[a]
                out.append('%04X: %-30s %-10s %s'
                           % (a, ' '.join('%02X' % b for b in self.M[a:a+min(ln,10)]), mn, o))
                a += ln
            else:
                st = a
                while a <= hi and a not in self.vm: a += 1
                for r in range(st, a, 16):
                    ch = self.M[r:min(a, r + 16)]
                    out.append('%04X: .db %-47s |%s|'
                               % (r, ' '.join('%02X' % b for b in ch),
                                  ''.join(chr(b) if 32 <= b < 127 else '.' for b in ch)))
        return '\n'.join(out)

    def native_listing(self, extra_entries=()):
        p = Prog(self.M, 0)
        ents = list(self.hw_prims()) + [0x0000, 0x0010, 0x0038, self.gateway,
                                        self.entry] + list(extra_entries)
        ents += [a for a, v in self.proc.items() if v == 'native']
        p.trace(ents)
        sel = {}
        for i, t in enumerate(self.hw_prims()): sel.setdefault(t, []).append(i)
        out = []
        for a in sorted(p.insns):
            if a in sel:
                out.append(''); out.append('===== HW PRIMITIVE %s  @%04X ====='
                                           % (','.join(str(s) for s in sel[a]), a))
            elif a in p.callrefs:
                out.append('; -- sub_%04X  <- %s'
                           % (a, ' '.join('%04X' % c for c in sorted(p.callrefs[a]))))
            elif a in p.xrefs:
                out.append('L%04X: ; <- %s'
                           % (a, ' '.join('%04X' % c for c in sorted(p.xrefs[a]))))
            i = p.insns[a]
            out.append('%04X: %-11s %s' % (a, ' '.join('%02x' % b for b in i.raw), i.text))
        return '\n'.join(out)


def main():
    ap = argparse.ArgumentParser(
        description='Disassemble the Philips VP415 module W LV-DOS firmware.',
        epilog='Give the two halves in order: LVDOS#1 then LVDOS#2, matched revisions.')
    ap.add_argument('lvdos1'); ap.add_argument('lvdos2')
    ap.add_argument('-o', '--out', default='disasm',
                    help='output directory (default: disasm)')
    ap.add_argument('-m', '--map', action='store_true',
                    help='print the layout summary only')
    args = ap.parse_args()

    data = open(args.lvdos1, 'rb').read() + open(args.lvdos2, 'rb').read()
    d = LvDos(data)
    d.trace()

    overlaps = sum(1 for a, (ln, *_) in d.vm.items()
                   for k in range(a + 1, a + ln) if k in d.vm)
    procs = [t for t, v in d.proc.items() if isinstance(v, tuple) or v == 'entry']

    print('p-code interpreter fetch loop  $%04X' % d.fetch)
    print('  IP variable                  $%04X' % d.ip_var)
    print('  opcode dispatch table        $%04X' % d.disp_tab)
    print('procedure prologue             $%04X   (call signature %s)'
          % (d.prologue, ' '.join('%02X' % b for b in d.sig)))
    print('p-code entry point             $%04X' % d.entry)
    print('native gateway                 $%04X' % d.gateway)
    print('  hardware jump table          $%04X   (%d selectors)'
          % (d.hw_tab, len(d.hw_prims())))
    print('p-code procedures found        %d' % len(procs))
    print('p-code instructions decoded    %d  (%d bytes, %d overlaps)'
          % (len(d.vm), sum(v[0] for v in d.vm.values()), overlaps))
    if args.map:
        for i, t in enumerate(d.hw_prims()):
            print('  selector %-3d -> $%04X' % (i, t))
        return

    os.makedirs(args.out, exist_ok=True)
    base = os.path.join(args.out, 'lvdos')
    with open(base + '-pcode.lst', 'w') as f: f.write(d.listing() + '\n')
    with open(base + '-native.lst', 'w') as f: f.write(d.native_listing() + '\n')
    print('wrote %s-pcode.lst and %s-native.lst' % (base, base))

if __name__ == '__main__':
    import os
    main()
