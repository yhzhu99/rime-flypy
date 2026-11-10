"""Exercise the real installed Rime C API against an isolated user directory."""
import ctypes as c
from pathlib import Path
import json
import os
import sys
import re
import shutil
import tempfile

sys.stdout.reconfigure(encoding='utf-8')

root = Path(__file__).resolve().parent.parent
if len(sys.argv) != 3:
    raise SystemExit("Usage: python tests/librime_behavior.py LIBRIME_LIBRARY SHARED_DATA_DIR")
dll_path = Path(sys.argv[1]).resolve()
shared_dir = Path(sys.argv[2]).resolve()
sandbox = tempfile.TemporaryDirectory(prefix="rime-flypy-test-")
user_dir = Path(sandbox.name)
for source in root.glob("*.yaml"):
    shutil.copy2(source, user_dir / source.name)
for directory in ("flypy", "lua"):
    shutil.copytree(root / directory, user_dir / directory)
if os.name == "nt":
    dll_directory = os.add_dll_directory(str(dll_path.parent))
dll = c.CDLL(str(dll_path))

class Traits(c.Structure):
    _fields_ = [('data_size', c.c_int)] + [(n, c.c_char_p) for n in (
        'shared_data_dir', 'user_data_dir', 'distribution_name', 'distribution_code_name',
        'distribution_version', 'app_name')] + [('modules', c.POINTER(c.c_char_p)),
        ('min_log_level', c.c_int), ('log_dir', c.c_char_p),
        ('prebuilt_data_dir', c.c_char_p), ('staging_dir', c.c_char_p)]

class Commit(c.Structure):
    _fields_ = [('data_size', c.c_int), ('text', c.c_char_p)]

class Status(c.Structure):
    _fields_ = [('data_size', c.c_int), ('schema_id', c.c_char_p), ('schema_name', c.c_char_p)] + [
        (n, c.c_int) for n in ('is_disabled', 'is_composing', 'is_ascii_mode', 'is_full_shape',
                            'is_simplified', 'is_traditional', 'is_ascii_punct')]

class Composition(c.Structure):
    _fields_ = [(n, c.c_int) for n in ('length', 'cursor_pos', 'sel_start', 'sel_end')] + [('preedit', c.c_char_p)]

class Candidate(c.Structure):
    _fields_ = [('text', c.c_char_p), ('comment', c.c_char_p), ('reserved', c.c_void_p)]

class Menu(c.Structure):
    _fields_ = [(n, c.c_int) for n in ('page_size', 'page_no', 'is_last_page', 'highlighted_candidate_index', 'num_candidates')] + [('candidates', c.POINTER(Candidate)), ('select_keys', c.c_char_p)]

class Context(c.Structure):
    _fields_ = [('data_size', c.c_int), ('composition', Composition), ('menu', Menu),
                ('commit_text_preview', c.c_char_p), ('select_labels', c.POINTER(c.c_char_p))]

def api(name, result, *args):
    fn = getattr(dll, name)
    fn.restype = result
    fn.argtypes = list(args)
    return fn

sid_t = c.c_size_t
setup = api('RimeSetup', None, c.POINTER(Traits))
initialize = api('RimeInitialize', None, c.POINTER(Traits))
finalize = api('RimeFinalize', None)
maintain = api('RimeStartMaintenance', c.c_int, c.c_int)
join = api('RimeJoinMaintenanceThread', None)
create = api('RimeCreateSession', sid_t)
select = api('RimeSelectSchema', c.c_int, sid_t, c.c_char_p)
process = api('RimeProcessKey', c.c_int, sid_t, c.c_int, c.c_int)
set_option = api('RimeSetOption', None, sid_t, c.c_char_p, c.c_int)
get_option = api('RimeGetOption', c.c_int, sid_t, c.c_char_p)
clear = api('RimeClearComposition', None, sid_t)
get_commit = api('RimeGetCommit', c.c_int, sid_t, c.POINTER(Commit))
free_commit = api('RimeFreeCommit', c.c_int, c.POINTER(Commit))
get_status = api('RimeGetStatus', c.c_int, sid_t, c.POINTER(Status))
free_status = api('RimeFreeStatus', c.c_int, c.POINTER(Status))
get_context = api('RimeGetContext', c.c_int, sid_t, c.POINTER(Context))
free_context = api('RimeFreeContext', c.c_int, c.POINTER(Context))

traits = Traits()
traits.data_size = c.sizeof(Traits) - c.sizeof(c.c_int)
traits.shared_data_dir = str(shared_dir).encode()
traits.user_data_dir = str(user_dir).encode()
traits.app_name = b'rime.shift_verification'
traits.min_log_level = 2
traits.log_dir = str(user_dir).encode()
setup(c.byref(traits))
initialize(c.byref(traits))


results=[]
try:
    if maintain(1): join()
    sid=create()
    assert sid and select(sid,b'flypy')
    def mode(): return bool(get_option(sid,b'ascii_mode'))
    def check(name,ok):
        assert ok,name
        results.append(name)
    def tap(key,mask=0):
        a=process(sid,key,mask)
        b=process(sid,key,(1<<30)|mask)
        return a,b
    def committed():
        value=Commit(); value.data_size=c.sizeof(Commit)-c.sizeof(c.c_int)
        if not get_commit(sid,c.byref(value)): return ''
        text=value.text.decode('utf8'); free_commit(c.byref(value)); return text
    def composing():
        status=Status(); status.data_size=c.sizeof(Status)-c.sizeof(c.c_int)
        assert get_status(sid,c.byref(status))
        result=bool(status.is_composing); free_status(c.byref(status)); return result
    for initial in (False,True):
        clear(sid); set_option(sid,b'ascii_mode',initial)
        check('F13 consumes press/release from '+str(initial),tap(0xffca)==(1,1))
        check('F13 selects Chinese from '+str(initial),not mode())
        tap(0xffca)
        check('Repeated F13 stays Chinese '+str(initial),not mode())
        tap(0xffe1,1)
        check('Left Shift selects English after F13 '+str(initial),mode())
        tap(0xffe1,1)
        check('Repeated left Shift stays English '+str(initial),mode())
        set_option(sid,b'ascii_mode',initial)
        for key,mask,label in [(0xffe2,1,'Right Shift'),(0xffe9,8,'Logical left Alt'),(0xffea,8,'Logical right Alt')]:
            tap(key,mask)
            check(label+' preserves mode '+str(initial),mode()==initial)
        process(sid,0xffe1,1); process(sid,ord('A'),1)
        process(sid,ord('A'),(1<<30)|1); process(sid,0xffe1,1<<30)
        check('Shift+A preserves mode '+str(initial),mode()==initial)
        committed()
    clear(sid); set_option(sid,b'ascii_mode',True); tap(0xffca)
    process(sid,ord('n'),0)
    check('Chinese input starts composing',composing())
    tap(0xffca)
    check('Repeated Chinese selection preserves composition',composing() and not mode())
    check('F13 does not prematurely commit',committed()=='')
    process(sid,ord(' '),0)
    text=committed()
    check('Chinese text commits after F13',text=='你')
    tap(0xffe1,1)
    check('English letter passes through after Shift',mode() and process(sid,ord('a'),0)==0)
    tap(0xffca)
    process(sid,ord('n'),0)
    check('Pending input before fixed English selection',composing())
    tap(0xffe1,1)
    check('Fixed English clears pending code',mode() and not composing())
    check('Fixed English does not commit pending code',committed()=='')
    tap(0xffca)
    for char in 'orq': process(sid,ord(char),0)
    context=Context();context.data_size=c.sizeof(Context)-c.sizeof(c.c_int)
    assert get_context(sid,c.byref(context))
    candidates=[context.menu.candidates[i].text.decode('utf8') for i in range(context.menu.num_candidates)]
    check('Existing Lua date translator works',any(re.fullmatch(r'\d{4}年\d{2}月\d{2}日',x) for x in candidates))
    free_context(c.byref(context));clear(sid)
    report={'passed':len(results),'scope':'Real librime library with an isolated repository configuration. No OS keyboard events are injected.','tests':results,'chinese_output':text}
    print(json.dumps(report,ensure_ascii=False,indent=2))
finally:
    finalize()
    sandbox.cleanup()
