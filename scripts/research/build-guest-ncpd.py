#!/usr/bin/env python3
"""Rebuild ncpd's Largedaemon from preserved source, in-guest, with
narrowly-scoped host-106 evidence records.  ``PBTRACE`` exposes protocol
queueing, transmission, and control-link RFNM processing.  ``SKTRACE``
exposes returned host-host decoding, socket requests and candidates,
match decisions and transitions, and kernel setup/modify/ready writes.
The records do not change daemon semantics, the external simulator,
topology, firmware, ITS configuration, or adapter behavior.

An earlier version of this builder cleared rfnm_bm immediately after
chk_host() sent its defensive RST.  That compatibility patch was based
on runs made before the IMP11-A output-order correction, when the RST
never reached the addressed IMP and therefore could not earn an RFNM.
The exact ``imp11a-telnet-pbtrace-20260831T160605Z`` rerun against the
corrected adapter proved that the clear changed only rfnm_bm: it left
the sent RST in h_pb_q and h_pb_sent, so send_pro() counted the RST a
second time beside the RFC and ir_rfnm() later saw three sent buffers
but only two queue elements.  This builder no longer makes the old
semantic kr_dcode.c change; its current kr_dcode.c patch is trace-only.
The corrected adapter returns the RST's real RFNM, allowing the preserved
daemon to retire that buffer before sending the queued RFC through its
original accounting path.

Builds all fourteen ncpd/*.c files plus skt_off.s and swab.s with V6's
own cc, entirely in-guest, reusing the technique already proven for
the guest TELNET client (see build-guest-telnet.py): this source's own
historical build recipe (ncpd/compile) expects NOSC's own
/nosc/conf/cc -L search path spanning ncpd/ and h/, which does not
exist on this guest image, so every header this source needs is
staged flat into one directory instead of trying to reproduce that
local path convention. Installs the result over the existing
prelinked /usr/net/etc/Largedaemon (smalldaemon execv()s that same
path, so it needs no separate rebuild).

One real archive gap turned up compiling this source, not caused by
the patch above: ncpd/send_pro.c's rst_all() calls getl() (read one
line from a struct io_buf) to parse /usr/net/hnames, and no
definition of getl() exists anywhere in this preserved tree -- it
must have lived in a local NOSC utility library (plausibly the "-lj"
this source's own linkit recipe links against) that was never
captured. Left unresolved, V6's ld still produces an a.out but with
an "Undefined: _getl" this guest's exec() then refuses to run at all
(smalldaemon's own "Exec of large daemon failed" is what that looks
like from the console) -- so this is fatal here even though rst_all()
only reaches getl() when /usr/net/hnames exists (it does not on this
image; fopen() fails first and that whole loop is skipped at
runtime). GETL_STUB below is a minimal, clearly-marked stand-in
supplying only what the linker needs, not a reconstruction of NOSC's
real one -- correct on this image only because the code path that
would call it for real is never reached here.

Research-phase tool: exploratory, not wired into any make target or
test.
"""
from __future__ import annotations

import argparse
import shutil
import sys
import time
from pathlib import Path

import pexpect

sys.path.insert(0, str(Path(__file__).resolve().parent))
from v6fs import V6FS  # noqa: E402

NCPD_C_FILES = [
    "1main.c", "kr_dcode.c", "ir_proc.c", "hr_proc.c",
    "assign.c", "files.c", "hstat.c", "kwrite.c",
    "send_pro.c", "skt_oper.c", "skt_util.c",
    "so_unm.c", "logstat.c", "util.c",
]
NCPD_S_FILES = ["skt_off.s", "swab.s"]
NCPD_H_FILES = [
    "files.h", "globvar.h", "hhi.h", "hstlnk.h", "impi.h",
    "kread.h", "kwrite.h", "leader.h", "measure.h", "probuf.h",
    "socket.h",
]
# Not under ncpd/ in the preserved tree -- these live in the shared h/
# directory (matching the same "system-wide headers live one level up"
# layout build-guest-telnet.py already navigated for net/*.h).
SHARED_H_FILES = ["io_buf.h", "param.h", "user.h"]

# brfid: linker-only stand-in for the missing getl() -- see the module
# docstring for why this is safe on this image and what it is not.
GETL_STUB_C = """/* brfid: minimal stand-in for a missing archive utility.
 * See build-guest-ncpd.py's own module docstring for why this exists
 * and why an unconditional failure return is correct here: rst_all()
 * (send_pro.c) only calls getl() after a successful fopen() of
 * /usr/net/hnames, which does not exist on this image, so this body
 * is never actually reached at runtime -- it exists purely to give
 * the linker a definition to resolve. Not a reconstruction of NOSC's
 * real getl().
 */
getl(line, fbuf)
char *line;
int *fbuf;
{
\treturn(-1);
}
"""

# Exact preserved-source anchors for the staged evidence trace.  The
# external source remains in the laboratory; this repository retains
# only the small mechanical instrumentation insertions below.
NCPD_PATCHES = {
    "send_pro.c": [
        (
            "\t/* check rfnm bit, return if set */\n"
            "\tif ( bit_on(&rfnm_bm[0],host) )\t\t/* rfnm outstanding for host? */\n",
            "\tif (host == 0106)\n"
            "\t\tprintf(\"PBTRACE send-enter h=%o sent=%d q=%o first=%o rfnm=%d\\n\",\n"
            "\t\t\thost,h_pb_sent[host],h_pb_q[host],\n"
            "\t\t\th_pb_q[host] ? h_pb_q[host]->pb_link : 0,\n"
            "\t\t\tbit_on(&rfnm_bm[0],host) != 0);\n"
            "\t/* check rfnm bit, return if set */\n"
            "\tif ( bit_on(&rfnm_bm[0],host) )\t\t/* rfnm outstanding for host? */\n",
        ),
        (
            "\t\t\th_pb_sent[host]++;\t/* inc probufs sent count */\n",
            "\t\t\th_pb_sent[host]++;\t/* inc probufs sent count */\n"
            "\t\t\tif (host == 0106)\n"
            "\t\t\t\tprintf(\"PBTRACE send-copy h=%o op=%o sent=%d q=%o\\n\",\n"
            "\t\t\t\t\thost,pb_p->pb_text[0]&0377,\n"
            "\t\t\t\t\th_pb_sent[host],h_pb_q[host]);\n",
        ),
        (
            "\tq_enter(&h_pb_q[host],pb_p);\t/* enter probuf in host's probuf q */\n"
            "\tpro2send = 1;\t\t\t/* set send flag */\n",
            "\tq_enter(&h_pb_q[host],pb_p);\t/* enter probuf in host's probuf q */\n"
            "\tif (host == 0106)\n"
            "\t\tprintf(\"PBTRACE queue h=%o op=%o sent=%d q=%o first=%o\\n\",\n"
            "\t\t\thost,pb_p->pb_text[0]&0377,h_pb_sent[host],\n"
            "\t\t\th_pb_q[host],h_pb_q[host]->pb_link);\n"
            "\tpro2send = 1;\t\t\t/* set send flag */\n",
        ),
    ],
    "ir_proc.c": [
        (
            "\th_pb_rtry[h] = 0;\t\t/* set retry count to zero */\n"
            "\treset_bit(&rfnm_bm[0],h);\t/* reset host's rfnm bit */\n",
            "\tif (h == 0106)\n"
            "\t\tprintf(\"PBTRACE rfnm-enter h=%o sent=%d q=%o first=%o\\n\",\n"
            "\t\t\th,h_pb_sent[h],h_pb_q[h],\n"
            "\t\t\th_pb_q[h] ? h_pb_q[h]->pb_link : 0);\n"
            "\th_pb_rtry[h] = 0;\t\t/* set retry count to zero */\n"
            "\treset_bit(&rfnm_bm[0],h);\t/* reset host's rfnm bit */\n",
        ),
        (
            "\twhile ( h_pb_sent[h] )\t\t/* loop while probufs sent != 0 */\n"
            "\t{\n"
            "\t\tq_enter(&pb_fr_q,q_dlink(&h_pb_q[h]));\n",
            "\twhile ( h_pb_sent[h] )\t\t/* loop while probufs sent != 0 */\n"
            "\t{\n"
            "\t\tif (h == 0106)\n"
            "\t\t\tprintf(\"PBTRACE rfnm-free h=%o sent=%d q=%o first=%o\\n\",\n"
            "\t\t\t\th,h_pb_sent[h],h_pb_q[h],\n"
            "\t\t\t\th_pb_q[h] ? h_pb_q[h]->pb_link : 0);\n"
            "\t\tq_enter(&pb_fr_q,q_dlink(&h_pb_q[h]));\n",
        ),
        (
            "\tif ( h_pb_q[h] != 0 )\t\t/* still have prbufs to send? */\n",
            "\tif (h == 0106)\n"
            "\t\tprintf(\"PBTRACE rfnm-done h=%o sent=%d q=%o\\n\",\n"
            "\t\t\th,h_pb_sent[h],h_pb_q[h]);\n"
            "\tif ( h_pb_q[h] != 0 )\t\t/* still have prbufs to send? */\n",
        ),
    ],
    "hr_proc.c": [
        (
            "\t\tif ( (op = *kr_p&0377) > hhi_rrp )\t/* illegal opcode? */\n",
            "\t\top = *kr_p&0377;\n"
            "\t\tif (host == 0106)\n"
            "\t\t\tprintf(\"SKTRACE hh h=%o bytes=%d op=%o\\n\",\n"
            "\t\t\t\thost,kr_bytes,op);\n"
            "\t\tif ( op > hhi_rrp )\t/* illegal opcode? */\n",
        ),
        (
            "\tp = kr_p;\t\t\t/* get copy of input stream pointer */\n"
            "\tif ( ((p->fskt3^p->lskt3)&1) == 0\t/* bad polarity btw skts? */\n",
            "\tp = kr_p;\t\t\t/* get copy of input stream pointer */\n"
            "\tif (host == 0106)\n"
            "\t{\n"
            "\t\tprintf(\"SKTRACE rfc h=%o op=%o fs=%o,%o,%o,%o\\n\",\n"
            "\t\t\thost,p->op&0377,p->fskt0&0377,p->fskt1&0377,\n"
            "\t\t\tp->fskt2&0377,p->fskt3&0377);\n"
            "\t\tprintf(\"SKTRACE rfc ls=%o,%o,%o,%o lnkbs=%o\\n\",\n"
            "\t\t\tp->lskt0&0377,p->lskt1&0377,p->lskt2&0377,\n"
            "\t\t\tp->lskt3&0377,p->lnk_bs&0377);\n"
            "\t}\n"
            "\tif ( ((p->fskt3^p->lskt3)&1) == 0\t/* bad polarity btw skts? */\n",
        ),
        (
            "\tp = kr_p;\t\t/* get copy of command stream pointer */\n"
            "\tif ( ((p->fskt3^p->lskt3)&1) == 0 )\t/* bad socket polarity? */\n",
            "\tp = kr_p;\t\t/* get copy of command stream pointer */\n"
            "\tif (host == 0106)\n"
            "\t{\n"
            "\t\tprintf(\"SKTRACE cls h=%o fs=%o,%o,%o,%o\\n\",\n"
            "\t\t\thost,p->fskt0&0377,p->fskt1&0377,\n"
            "\t\t\tp->fskt2&0377,p->fskt3&0377);\n"
            "\t\tprintf(\"SKTRACE cls ls=%o,%o,%o,%o\\n\",\n"
            "\t\t\tp->lskt0&0377,p->lskt1&0377,\n"
            "\t\t\tp->lskt2&0377,p->lskt3&0377);\n"
            "\t}\n"
            "\tif ( ((p->fskt3^p->lskt3)&1) == 0 )\t/* bad socket polarity? */\n",
        ),
        (
            "\tp = kr_p;\n"
            "\tif ( (s_p = hl_find( host|((p[1]|0200)<<8) )) != 0 )\n",
            "\tp = kr_p;\n"
            "\tif (host == 0106)\n"
            "\t\tprintf(\"SKTRACE all h=%o link=%o msgs=%o,%o bits=%o,%o,%o,%o\\n\",\n"
            "\t\t\thost,p[1]&0377,p[2]&0377,p[3]&0377,\n"
            "\t\t\tp[4]&0377,p[5]&0377,p[6]&0377,p[7]&0377);\n"
            "\tif ( (s_p = hl_find( host|((p[1]|0200)<<8) )) != 0 )\n",
        ),
    ],
    "kr_dcode.c": [
        (
            "\tfp->f_state = fs_uiopw;\t\t\t/* file state is user icp open\n"
            "\t\t\t\t\t\t   wait */\n",
            "\tfp->f_state = fs_uiopw;\t\t\t/* file state is user icp open\n"
            "\t\t\t\t\t\t   wait */\n"
            "\tif (host == 0106)\n"
            "\t{\n"
            "\t\tprintf(\"SKTRACE ouicp id=%o st=%d ls=%o,%o h=%o l=%o\\n\",\n"
            "\t\t\tfp->f_id,skt_req.s_state,skt_req.s_lskt[0]&0377,\n"
            "\t\t\tskt_req.s_lskt[1]&0377,skt_req.s_hstlnk.hl_host&0377,\n"
            "\t\t\tskt_req.s_hstlnk.hl_link&0377);\n"
            "\t\tprintf(\"SKTRACE ouicp fs=%o,%o,%o,%o sinx=%d fstate=%d\\n\",\n"
            "\t\t\tskt_req.s_fskt[0]&0377,skt_req.s_fskt[1]&0377,\n"
            "\t\t\tskt_req.s_fskt[2]&0377,skt_req.s_fskt[3]&0377,\n"
            "\t\t\tskt_req.s_sinx,fp->f_state);\n"
            "\t}\n",
        ),
    ],
    "skt_util.c": [
        (
            "\tfor ( p = &sockets[0] ; p < &sockets[nsockets] ; p++ )\t/* loop thru \n"
            "\t\t\t\t\t\t\t\t   all skts */\n"
            "\t\tif ( (p->s_state != ss_null)\t\t/* socket in use? */\n"
            "\t\t     && (p->s_lskt->word == skt_req.s_lskt->word) )\n"
            "\t\t\t\t\t\t\t/* and locals match? */\n"
            "\t\t\tif ( (*skt_oper[skt_req.s_state][p->s_state])(p) )\n"
            "\t\t\t\t/* did op procedure return non-zero? */\n"
            "\t\t\t\treturn;\t\t/* all done if so */\n"
            "\t(*so_unm[skt_req.s_state])(p);\t/* if fell out of loop, no match,\n",
            "\tif (skt_req.s_hstlnk.hl_host == 0106)\n"
            "\t{\n"
            "\t\tprintf(\"SKTRACE get reqst=%d ls=%o,%o h=%o l=%o\\n\",\n"
            "\t\t\tskt_req.s_state,skt_req.s_lskt[0]&0377,\n"
            "\t\t\tskt_req.s_lskt[1]&0377,skt_req.s_hstlnk.hl_host&0377,\n"
            "\t\t\tskt_req.s_hstlnk.hl_link&0377);\n"
            "\t\tprintf(\"SKTRACE get reqfs=%o,%o,%o,%o owner=%o sinx=%d\\n\",\n"
            "\t\t\tskt_req.s_fskt[0]&0377,skt_req.s_fskt[1]&0377,\n"
            "\t\t\tskt_req.s_fskt[2]&0377,skt_req.s_fskt[3]&0377,\n"
            "\t\t\tskt_req.s_filep ? skt_req.s_filep->f_id : 0,\n"
            "\t\t\tskt_req.s_sinx);\n"
            "\t}\n"
            "\tfor ( p = &sockets[0] ; p < &sockets[nsockets] ; p++ )\t/* loop thru\n"
            "\t\t\t\t\t\t\t\t   all skts */\n"
            "\t{\n"
            "\t\tif ((skt_req.s_hstlnk.hl_host == 0106) &&\n"
            "\t\t    (p->s_state != ss_null))\n"
            "\t\t{\n"
            "\t\t\tprintf(\"SKTRACE cand i=%d st=%d owner=%o ls=%o,%o h=%o l=%o\\n\",\n"
            "\t\t\t\tp-&sockets[0],p->s_state,\n"
            "\t\t\t\tp->s_filep ? p->s_filep->f_id : 0,\n"
            "\t\t\t\tp->s_lskt[0]&0377,p->s_lskt[1]&0377,\n"
            "\t\t\t\tp->s_hstlnk.hl_host&0377,p->s_hstlnk.hl_link&0377);\n"
            "\t\t\tprintf(\"SKTRACE cand fs=%o,%o,%o,%o localmatch=%d sinx=%d\\n\",\n"
            "\t\t\t\tp->s_fskt[0]&0377,p->s_fskt[1]&0377,\n"
            "\t\t\t\tp->s_fskt[2]&0377,p->s_fskt[3]&0377,\n"
            "\t\t\t\tp->s_lskt->word == skt_req.s_lskt->word,p->s_sinx);\n"
            "\t\t}\n"
            "\t\tif ( (p->s_state != ss_null)\t\t/* socket in use? */\n"
            "\t\t     && (p->s_lskt->word == skt_req.s_lskt->word) )\n"
            "\t\t\t\t\t\t\t/* and locals match? */\n"
            "\t\t\tif ( (*skt_oper[skt_req.s_state][p->s_state])(p) )\n"
            "\t\t\t\t/* did op procedure return non-zero? */\n"
            "\t\t\t\treturn;\t\t/* all done if so */\n"
            "\t}\n"
            "\tif (skt_req.s_hstlnk.hl_host == 0106)\n"
            "\t\tprintf(\"SKTRACE get unmatched reqst=%d\\n\",skt_req.s_state);\n"
            "\t(*so_unm[skt_req.s_state])(p);\t/* if fell out of loop, no match,\n",
        ),
    ],
    "skt_oper.c": [
        (
            "int\tso_match(skt_p)\n"
            "struct socket\t*skt_p;\n"
            "{\n"
            "\tif ( skt_req.s_hstlnk.hl_host != skt_p->s_hstlnk.hl_host )\n"
            "\t\t\t/* hosts not equal? */\n"
            "\t\treturn(0);\n"
            "\treturn ( so_fseq ( &skt_req.lo_byte, skt_p ) );\t/* return result of \n"
            "\t\t\t\t\t\t   compare of foreign sockets */\n"
            "}\n",
            "int\tso_match(skt_p)\n"
            "struct socket\t*skt_p;\n"
            "{\n"
            "\tregister int fmatch;\n"
            "\n"
            "\tif ( skt_req.s_hstlnk.hl_host != skt_p->s_hstlnk.hl_host )\n"
            "\t{\n"
            "\t\tif (skt_req.s_hstlnk.hl_host == 0106)\n"
            "\t\t\tprintf(\"SKTRACE match i=%d host=0 reqh=%o candh=%o\\n\",\n"
            "\t\t\t\tskt_p-&sockets[0],skt_req.s_hstlnk.hl_host&0377,\n"
            "\t\t\t\tskt_p->s_hstlnk.hl_host&0377);\n"
            "\t\treturn(0);\n"
            "\t}\n"
            "\tfmatch = so_fseq ( &skt_req.lo_byte, skt_p );\n"
            "\tif (skt_req.s_hstlnk.hl_host == 0106)\n"
            "\t\tprintf(\"SKTRACE match i=%d host=1 foreign=%d\\n\",\n"
            "\t\t\tskt_p-&sockets[0],fmatch);\n"
            "\treturn ( fmatch );\n"
            "}\n",
        ),
        (
            "\t\ts_p->s_state = ss_open;\t/* set socket state to open */\n"
            "\t\treturn(1);\t\t/* all done successfully */\n",
            "\t\ts_p->s_state = ss_open;\t/* set socket state to open */\n"
            "\t\tif (skt_req.s_hstlnk.hl_host == 0106)\n"
            "\t\t\tprintf(\"SKTRACE transition i=%d rfcw->open link=%o bsz=%o\\n\",\n"
            "\t\t\t\ts_p-&sockets[0],s_p->s_hstlnk.hl_link&0377,\n"
            "\t\t\t\ts_p->s_bysz&0377);\n"
            "\t\treturn(1);\t\t/* all done successfully */\n",
        ),
        (
            "\tif ( rfc_util ( skt_p ) )\t/* match found via rfc_util? */\n"
            "\t{\n"
            "\t\tfi_sopn ( skt_p );\t/* pass to file level */\n",
            "\tif ( rfc_util ( skt_p ) )\t/* match found via rfc_util? */\n"
            "\t{\n"
            "\t\tif (skt_req.s_hstlnk.hl_host == 0106)\n"
            "\t\t\tprintf(\"SKTRACE rfc-rfcw i=%d fi_sopn owner=%o\\n\",\n"
            "\t\t\t\tskt_p-&sockets[0],\n"
            "\t\t\t\tskt_p->s_filep ? skt_p->s_filep->f_id : 0);\n"
            "\t\tfi_sopn ( skt_p );\t/* pass to file level */\n",
        ),
    ],
    "so_unm.c": [
        (
            "\t\t\tif ( skt_req.s_state == si_rfc )\t/* real rfc? */\n"
            "\t\t\t\tn_s_left--;\t\t/* decrement socket\n",
            "\t\t\tif (skt_req.s_hstlnk.hl_host == 0106)\n"
            "\t\t\t\tprintf(\"SKTRACE alloc i=%d st=%d owner=%o ls=%o,%o\\n\",\n"
            "\t\t\t\t\ts_p-&sockets[0],s_p->s_state,\n"
            "\t\t\t\t\ts_p->s_filep ? s_p->s_filep->f_id : 0,\n"
            "\t\t\t\t\ts_p->s_lskt[0]&0377,s_p->s_lskt[1]&0377);\n"
            "\t\t\tif ( skt_req.s_state == si_rfc )\t/* real rfc? */\n"
            "\t\t\t\tn_s_left--;\t\t/* decrement socket\n",
        ),
    ],
    "kwrite.c": [
        (
            "\tkw_buf.kw_data->mb_fskt[1] = swab( p->s_fskt[2].word );\t/* frn skt */\n"
            "\treturn( kw_write(&kw_buf.kw_data->mb_fskt[2].lo_byte\n",
            "\tkw_buf.kw_data->mb_fskt[1] = swab( p->s_fskt[2].word );\t/* frn skt */\n"
            "\tif (p->s_hstlnk.hl_host == 0106)\n"
            "\t{\n"
            "\t\tprintf(\"SKTRACE kw op=%d id=%o sinx=%d h=%o l=%o stat=%o bsz=%o\\n\",\n"
            "\t\t\top,p->s_filep->f_id,p->s_sinx,\n"
            "\t\t\tp->s_hstlnk.hl_host&0377,p->s_hstlnk.hl_link&0377,\n"
            "\t\t\tstatus,p->s_bysz&0377);\n"
            "\t\tprintf(\"SKTRACE kw ls=%o,%o fs=%o,%o,%o,%o\\n\",\n"
            "\t\t\tp->s_lskt[0]&0377,p->s_lskt[1]&0377,\n"
            "\t\t\tp->s_fskt[0]&0377,p->s_fskt[1]&0377,\n"
            "\t\t\tp->s_fskt[2]&0377,p->s_fskt[3]&0377);\n"
            "\t}\n"
            "\treturn( kw_write(&kw_buf.kw_data->mb_fskt[2].lo_byte\n",
        ),
        (
            "\tkw_buf.kw_stat = code;\t\t/* ready code */\n"
            "\treturn( kw_write(&kw_buf.kw_data[0]-&kw_buf.lo_byte) );\n",
            "\tkw_buf.kw_stat = code;\t\t/* ready code */\n"
            "\tprintf(\"SKTRACE kw-ready id=%o code=%o\\n\",id,code);\n"
            "\treturn( kw_write(&kw_buf.kw_data[0]-&kw_buf.lo_byte) );\n",
        ),
    ],
}


def stage_sources(network_unix_v6_root: Path, stage_dir: Path) -> None:
    if stage_dir.exists() and any(stage_dir.iterdir()):
        raise RuntimeError(f"staging directory is not empty: {stage_dir}")
    stage_dir.mkdir(parents=True, exist_ok=True)
    ncpd = network_unix_v6_root / "nosc-files" / "ncpd"
    h = network_unix_v6_root / "nosc-files" / "h"

    for name in NCPD_C_FILES + NCPD_S_FILES + NCPD_H_FILES:
        shutil.copy(ncpd / name, stage_dir / name)
    for name in SHARED_H_FILES:
        shutil.copy(h / name, stage_dir / name)
    (stage_dir / "getl_stub.c").write_text(GETL_STUB_C)

    for filename, patches in NCPD_PATCHES.items():
        path = stage_dir / filename
        text = path.read_text()
        for old, new in patches:
            if old not in text:
                raise RuntimeError(
                    f"{filename}: expected anchor text not found -- "
                    f"preserved source may not match what this patch "
                    f"was written against: {old!r}")
            text = text.replace(old, new, 1)
        path.write_text(text)


def inject(image: Path, stage_dir: Path) -> None:
    fs = V6FS(str(image))
    if fs.lookup("/tmp/ncpd") is not None:
        raise RuntimeError("guest image already contains /tmp/ncpd; use a fresh build image")
    fs.mkdir("/tmp/ncpd")
    for path in sorted(stage_dir.iterdir()):
        fs.put_file("/tmp/ncpd", path.name, path.read_bytes())
    fs.clear_inode_cache()
    fs.flush_superblock()
    fs.save()


def guest_command(child: pexpect.spawn, text: str, timeout: float) -> str:
    """Run one command under the preserved V6 shell and return its output."""
    child.send(f"{text}\r")
    child.expect_exact("\r\n# ", timeout=timeout)
    return child.before.replace("\r", "")


def ls_records(output: str) -> dict[str, str]:
    """Extract concrete V6 ls(1) records from command output."""
    records = {}
    for line in output.splitlines():
        fields = line.split()
        mode = fields[0] if fields else ""
        if (len(fields) >= 4 and len(mode) == 10 and mode[0] in "-bcd"
                and set(mode[1:]) <= set("rwx-")):
            records[fields[-1]] = line
    return records


def require_files(child: pexpect.spawn, paths: list[str], timeout: float = 30) -> dict[str, str]:
    """Require fresh guest artifacts through their concrete ls(1) records."""
    output = guest_command(child, f"ls -l {' '.join(paths)}", timeout)
    records = ls_records(output)
    missing = [path for path in paths if path not in records]
    if missing:
        raise RuntimeError(f"guest build did not produce {missing!r}:\n{output}")
    return records


def require_missing(child: pexpect.spawn, path: str, timeout: float = 30) -> None:
    """Require that a removed guest artifact has no concrete ls(1) record."""
    output = guest_command(child, f"ls -l {path}", timeout)
    if path in ls_records(output):
        raise RuntimeError(f"guest artifact still exists after removal: {path}\n{output}")


def reject_tool_errors(label: str, output: str) -> None:
    lowered = output.lower()
    if any(word in lowered for word in ("error", "fatal", "undefined", "can't", "cannot")):
        raise RuntimeError(f"{label} reported an error:\n{output}")


def build_in_guest(pdp11: Path, workdir: Path, console_log: Path, settle: float) -> None:
    console = open(console_log, "w")
    child = pexpect.spawn(str(pdp11), cwd=str(workdir), timeout=60, encoding="utf-8")
    child.logfile = console
    try:
        build_in_guest_session(child, settle)
    finally:
        if child.isalive():
            child.close(force=True)
        console.close()


def build_in_guest_session(child: pexpect.spawn, settle: float) -> None:

    child.sendline("set cpu 11/34 256k")
    child.sendline("set rl0 rl01")
    child.sendline("set rl1 rl01")
    child.sendline("attach rl0 images/ncp_root.rl01")
    child.sendline("attach rl1 images/ncp_swap.rl01")
    child.sendline("boot rl0")
    child.expect("!", timeout=15)
    time.sleep(0.5)
    child.send("green\r")
    child.expect("login:", timeout=30)
    time.sleep(0.5)
    child.send("root\r")
    child.expect("#", timeout=10)
    time.sleep(1.0)

    child.send("chdir /tmp/ncpd\r")
    child.expect_exact("\r\n# ", timeout=10)
    child.send("pwd\r")
    child.expect_exact("/tmp/ncpd", timeout=10)
    child.expect_exact("\r\n# ", timeout=10)
    stale_objects = " ".join(
        [f"{Path(name).stem}.o" for name in NCPD_C_FILES + ["getl_stub.c"]]
        + ["skt_off.o", "swab.o"]
    )
    guest_command(child, f"rm -f a.out {stale_objects}", 10)

    for name in ("skt_off", "swab"):
        print(f"[build] assembling {name}.s", file=sys.stderr)
        # This preserved as(1) produces a valid a.out but returns a nonzero
        # status even on success.  Stale a.out was removed above, so require
        # the new artifact explicitly rather than accepting the status.
        output = guest_command(child, f"as {name}.s", 60)
        reject_tool_errors(f"assembling {name}.s", output)
        require_files(child, ["a.out"], 10)
        guest_command(child, f"mv a.out {name}.o", 10)
        require_files(child, [f"{name}.o"], 10)

    all_c_files = NCPD_C_FILES + ["getl_stub.c"]
    c_files = " ".join(all_c_files)
    print(f"[build] compiling {len(all_c_files)} ncpd sources (this takes a while)",
          file=sys.stderr)
    compile_output = guest_command(child, f"cc -O -c {c_files}", 600)
    reject_tool_errors("compiling ncpd", compile_output)

    print("[build] listing produced object files", file=sys.stderr)
    expected_objects = " ".join(
        [f"{Path(name).stem}.o" for name in all_c_files] + ["skt_off.o", "swab.o"]
    )
    require_files(child, expected_objects.split(), 30)

    # No -n here: ncpd/linkit (this source's own historical link recipe)
    # calls ld directly with no -n either, producing a normal (impure)
    # a.out. A first attempt at -n -x (matching build-guest-telnet.py's
    # single-file build, which does compile and link in one step) linked
    # without any linker error but produced a "separate I&D" binary this
    # guest's exec() refused to run at all -- smalldaemon's own "Exec of
    # large daemon failed" is what that looks like from the console.
    # Matching the real recipe's plain link is the current attempt at
    # fixing that; see docs/research/imp11a-device.md for whether it did.
    o_files = " ".join(f"{Path(name).stem}.o" for name in all_c_files) + " skt_off.o swab.o"
    print("[build] linking Largedaemon", file=sys.stderr)
    guest_command(child, "rm -f a.out", 10)
    link_output = guest_command(child, f"cc -O -x {o_files}", 120)
    reject_tool_errors("linking Largedaemon", link_output)
    linked = require_files(child, ["a.out"], 15)

    # Remove the prelinked daemon and prove it is gone before copying the
    # fresh artifact.  Otherwise a failed cp could leave the old daemon in
    # place and let the owner/mode checks below report a false success.
    guest_command(child, "rm -f /usr/net/etc/Largedaemon", 10)
    require_missing(child, "/usr/net/etc/Largedaemon", 10)
    guest_command(child, "cp a.out /usr/net/etc/Largedaemon", 10)
    # ncpd/linkit's own install step does exactly this three-command
    # sequence. This image has no `system` entry for the recipe's chgrp
    # command, and mode 544 grants execute only to the owner. smalldaemon.c
    # calls setuid(1) before exec, so the material requirement here is owner
    # `daemon` plus mode 544; require both from the final concrete ls record.
    guest_command(child, "chown daemon /usr/net/etc/Largedaemon", 10)
    guest_command(child, "chmod 544 /usr/net/etc/Largedaemon", 10)
    installed = require_files(child, ["/usr/net/etc/Largedaemon"], 10)
    installed_fields = installed["/usr/net/etc/Largedaemon"].split()
    if installed_fields[0] != "-r-xr--r--" or installed_fields[2] != "daemon":
        raise RuntimeError(
            "installed Largedaemon has the wrong mode or owner: "
            + installed["/usr/net/etc/Largedaemon"]
        )
    linked_fields = linked["a.out"].split()
    if installed_fields[3] != linked_fields[3]:
        raise RuntimeError(
            "installed Largedaemon size does not match linked a.out: "
            + installed["/usr/net/etc/Largedaemon"]
            + " != " + linked["a.out"]
        )
    guest_command(child, "sync", 10)
    time.sleep(settle)

    print("[build] shutting down cleanly", file=sys.stderr)
    child.sendcontrol("e")
    time.sleep(0.5)
    child.sendline("quit")
    try:
        child.expect(pexpect.EOF, timeout=15)
    except pexpect.TIMEOUT:
        print("[build] simh did not exit on its own, forcing", file=sys.stderr)
        child.close(force=True)


def _main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--network-unix-v6-root", required=True, type=Path,
        help="checkout of pdp11/network-unix-v6 (pins/sources.lock.toml)")
    p.add_argument(
        "--pdp11", required=True, type=Path,
        help="Open SIMH pdp11 binary built with the IMP11-A device")
    p.add_argument(
        "--root-image", required=True, type=Path,
        help="green/unix root RL01 image to modify in place (a copy, "
             "not the original) -- normally the output of "
             "build-guest-telnet.py, so the guest telnet client and "
             "the fixed daemon end up on the same image")
    p.add_argument(
        "--swap-image", required=True, type=Path,
        help="matching swap RL01 image")
    p.add_argument(
        "--work-dir", required=True, type=Path,
        help="scratch directory for staged sources and the guest console log")
    p.add_argument(
        "--settle", type=float, default=1.0,
        help="seconds to wait after sync before shutting down")
    args = p.parse_args()

    args.work_dir.mkdir(parents=True, exist_ok=True)
    stage_dir = args.work_dir / "stage"
    stage_sources(args.network_unix_v6_root, stage_dir)

    guest_dir = args.work_dir / "guest"
    (guest_dir / "images").mkdir(parents=True, exist_ok=True)
    root_image = guest_dir / "images" / "ncp_root.rl01"
    swap_image = guest_dir / "images" / "ncp_swap.rl01"
    shutil.copy(args.root_image, root_image)
    shutil.copy(args.swap_image, swap_image)

    print(f"[build] injecting ncpd sources into {root_image}", file=sys.stderr)
    inject(root_image, stage_dir)

    build_in_guest(
        args.pdp11, guest_dir,
        args.work_dir / "build-guest-ncpd.console.log", args.settle)

    print(f"[build] done. built root image: {root_image}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
