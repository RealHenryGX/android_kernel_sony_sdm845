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

# 4.9 fsnotify_alloc_group takes one arg (no flags) - the code already #if's on 6.0, fine.

if errors:
    print('ERRORS:')
    for e in errors:
        print(' -', e)
    sys.exit(1)
print('fix-ksu-v2-4.9: OK')
