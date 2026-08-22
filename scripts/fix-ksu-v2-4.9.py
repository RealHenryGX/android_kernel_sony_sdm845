#!/usr/bin/env python3
"""4.9 kernel compat fixes for KernelSU v2.1.2 (run in CI after integrating sources)."""

import os, re, sys

BASE = 'drivers/kernelsu'
errors = []

def patch_file(rel, old, new, count=1):
    p = os.path.join(BASE, rel)
    if not os.path.exists(p):
        errors.append(f'MISSING {p}')
        return
    s = open(p, encoding='utf-8', errors='replace').read()
    if old not in s:
        errors.append(f'PATTERN-NOT-FOUND in {rel}: {old[:60]!r}')
        return
    s = s.replace(old, new, count)
    open(p, 'w', encoding='utf-8', newline='\n').write(s)
    print(f'patched {rel}')

# ---- pkg_observer.c: 4.9 fsnotify_ops has only handle_event (5.1+ splits) ----
old_ops = """static const struct fsnotify_ops ksu_ops = {
    .handle_inode_event = ksu_handle_inode_event,
};"""
new_ops = """#if LINUX_VERSION_CODE >= KERNEL_VERSION(5, 1, 0)
static const struct fsnotify_ops ksu_ops = {
    .handle_inode_event = ksu_handle_inode_event,
};
#else
static int ksu_handle_event(struct fsnotify_group *group, struct inode *inode,
                            struct fsnotify_mark *inode_mark,
                            struct fsnotify_mark *vfsmnt_mark, u32 mask,
                            void *data, int data_type,
                            const unsigned char *file_name, u32 cookie)
{
    struct qstr q = { .name = file_name, .len = file_name ? strlen(file_name) : 0 };
    return ksu_handle_inode_event(inode_mark, mask, inode, NULL, &q, cookie);
}
static const struct fsnotify_ops ksu_ops = {
    .handle_event = ksu_handle_event,
};
#endif"""
patch_file('pkg_observer.c', old_ops, new_ops)

# 4.9 fsnotify_init_mark takes (mark, free_mark_cb) - group binding is 5.x+
patch_file('pkg_observer.c', 'fsnotify_init_mark(m, g);', 'fsnotify_init_mark(m, NULL);')

# ---- seccomp_cache.c: 5.x+ internals (refcount_t, SECCOMP_ARCH_NATIVE_NR, redefines
#      struct seccomp_filter) - disabled on 4.9 (pure optimization, setuid_hook still works)
patch_file('Makefile', 'kernelsu-objs += seccomp_cache.o\n', '')
patch_file('setuid_hook.c', '#include "seccomp_cache.h"\n', '')
patch_file('setuid_hook.c',
           '        ksu_seccomp_allow_cache(current->seccomp.filter, __NR_reboot);\n',
           '        /* 4.9: seccomp_cache disabled */\n')
patch_file('setuid_hook.c',
           '            ksu_seccomp_allow_cache(current->seccomp.filter, __NR_reboot);\n',
           '            /* 4.9: seccomp_cache disabled */\n')

# ---- file_wrapper.c: 4.9 file_operations lacks remap_file_range/fadvise/iopoll/mmap_supported_flags
import re as _re
_fw = 'file_wrapper.c'
_s = open(os.path.join(BASE, _fw), encoding='utf-8', errors='replace').read()
# drop the two 5.x-only wrapper functions (remap_file_range, fadvise)
_s = _re.sub(r'static loff_t ksu_wrapper_remap_file_range.*?\n\}\n\n', '', _s, flags=_re.S)
_s = _re.sub(r'static int ksu_wrapper_fadvise.*?\n\}\n\n', '', _s, flags=_re.S)
# drop 5.x-only fops assignments in ksu_create_file_wrapper
_s = _s.replace('\tp->ops.iopoll = fp->f_op->iopoll ? ksu_wrapper_iopoll : NULL;\n', '')
_s = _s.replace('''#if LINUX_VERSION_CODE >= KERNEL_VERSION(6, 12, 0)
	p->ops.fop_flags = fp->f_op->fop_flags;
#else
	p->ops.mmap_supported_flags = fp->f_op->mmap_supported_flags;
#endif
''', '')
_s = _s.replace('\tp->ops.remap_file_range = fp->f_op->remap_file_range ? ksu_wrapper_remap_file_range : NULL;\n', '')
_s = _s.replace('\tp->ops.fadvise = fp->f_op->fadvise ? ksu_wrapper_fadvise : NULL;\n', '')
# remove the whole iopoll wrapper (both #if/#else branches) - 4.9 fops has no iopoll member
_s = _re.sub(r'#if LINUX_VERSION_CODE >= KERNEL_VERSION\(6, 1, 0\)\nstatic int ksu_wrapper_iopoll.*?\n#endif\n', '', _s, flags=_re.S)
# __poll_t is 5.x+; 4.9 poll() returns unsigned int
_s = _s.replace('static __poll_t ksu_wrapper_poll', 'static unsigned int ksu_wrapper_poll')
# iopoll wrapper fn stays inside #if LINUX_VERSION_CODE >= 6.1 - not compiled on 4.9, no unused warning
open(os.path.join(BASE, _fw), 'w', encoding='utf-8', newline='\n').write(_s)
print('patched file_wrapper.c')

# ---- ksud.c: strncpy_from_user_nofault is 5.x+; 4.9 uses strncpy_from_user
patch_file('ksud.c', 'strncpy_from_user_nofault', 'strncpy_from_user')

# 4.9 fsnotify_alloc_group takes one arg (no flags) - the code already #if's on 6.0, fine.

if errors:
    print('ERRORS:')
    for e in errors:
        print(' -', e)
    sys.exit(1)
print('fix-ksu-v2-4.9: OK')
