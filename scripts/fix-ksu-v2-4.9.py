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

# ---- ksud.c etc: strncpy_from_user_nofault is 5.x+; 4.9 uses strncpy_from_user (ALL files, ALL occurrences)
for _f in os.listdir(os.path.join(BASE)):
    if _f.endswith('.c'):
        _p = os.path.join(BASE, _f)
        _s = open(_p, encoding='utf-8', errors='replace').read()
        if 'strncpy_from_user_nofault' in _s:
            open(_p, 'w', encoding='utf-8', newline='\n').write(
                _s.replace('strncpy_from_user_nofault', 'strncpy_from_user'))
            print(f'patched {_f} (nofault)')

# ---- selinux/selinux.c: selinux_state global is 5.x+; 4.9 no-op setenforce/getenforce=true
_sel = 'selinux/selinux.c'
_ss = open(os.path.join(BASE, _sel), encoding='utf-8', errors='replace').read()
_ss = _ss.replace('''void setenforce(bool enforce)
{
#ifdef CONFIG_SECURITY_SELINUX_DEVELOP
    selinux_state.enforcing = enforce;
#endif
}''', '''void setenforce(bool enforce)
{
#ifdef CONFIG_SECURITY_SELINUX_DEVELOP
#if LINUX_VERSION_CODE >= KERNEL_VERSION(5, 1, 0)
    selinux_state.enforcing = enforce;
#endif
#endif
}''')
_ss = _ss.replace('''bool getenforce()
{
#ifdef CONFIG_SECURITY_SELINUX_DISABLE
    if (selinux_state.disabled) {
        return false;
    }
#endif

#ifdef CONFIG_SECURITY_SELINUX_DEVELOP
    return selinux_state.enforcing;
#else
    return true;
#endif
}''', '''bool getenforce()
{
#if LINUX_VERSION_CODE >= KERNEL_VERSION(5, 1, 0)
#ifdef CONFIG_SECURITY_SELINUX_DISABLE
    if (selinux_state.disabled) {
        return false;
    }
#endif
#ifdef CONFIG_SECURITY_SELINUX_DEVELOP
    return selinux_state.enforcing;
#else
    return true;
#endif
#else
    return true;
#endif
}''')
_ss = _ss.replace('    return security_release_secctx(cp->context, cp->len);',
                  '    security_release_secctx(cp->context, cp->len);')

# ---- selinux domain helpers: selinux_cred/current_sid/__security_secid_to_secctx are 5.x+
#      internal APIs. On 4.9 return false (KSU su/auth does not depend on domain check).
_domain_old = '''bool is_task_ksu_domain(const struct cred* cred)
{
    struct lsm_context ctx;
    bool result;
    if (!cred) {
        return false;
    }
    const struct task_security_struct *tsec = selinux_cred(cred);
    if (!tsec) {
        return false;
    }
    int err = __security_secid_to_secctx(tsec->sid, &ctx);
    if (err) {
        return false;
    }
    result = strncmp(KERNEL_SU_DOMAIN, ctx.context, ctx.len) == 0;
    __security_release_secctx(&ctx);
    return result;
}'''
_domain_new = '''bool is_task_ksu_domain(const struct cred* cred)
{
#if LINUX_VERSION_CODE >= KERNEL_VERSION(5, 4, 0)
    struct lsm_context ctx;
    bool result;
    if (!cred) {
        return false;
    }
    const struct task_security_struct *tsec = selinux_cred(cred);
    if (!tsec) {
        return false;
    }
    int err = __security_secid_to_secctx(tsec->sid, &ctx);
    if (err) {
        return false;
    }
    result = strncmp(KERNEL_SU_DOMAIN, ctx.context, ctx.len) == 0;
    __security_release_secctx(&ctx);
    return result;
#else
    return false;
#endif
}'''
_ss = _ss.replace(_domain_old, _domain_new)
_ss = _ss.replace('''bool is_ksu_domain()
{
    current_sid();
    return is_task_ksu_domain(current_cred());
}''', '''bool is_ksu_domain()
{
#if LINUX_VERSION_CODE >= KERNEL_VERSION(5, 4, 0)
    current_sid();
#endif
    return is_task_ksu_domain(current_cred());
}''')
_ss = _re.sub(r'bool is_context\(const struct cred\* cred, const char\* context\)\n\{.*?\n\}\n',
'''bool is_context(const struct cred* cred, const char* context)
{
#if LINUX_VERSION_CODE >= KERNEL_VERSION(5, 4, 0)
    if (!cred) {
        return false;
    }
    const struct task_security_struct * tsec = selinux_cred(cred);
    if (!tsec) {
        return false;
    }
    struct lsm_context ctx;
    bool result;
    int err = __security_secid_to_secctx(tsec->sid, &ctx);
    if (err) {
        return false;
    }
    result = strncmp(context, ctx.context, ctx.len) == 0;
    __security_release_secctx(&ctx);
    return result;
#else
    return false;
#endif
}
''', _ss, count=1, flags=_re.S)
open(os.path.join(BASE, _sel), 'w', encoding='utf-8', newline='\n').write(_ss)
print('patched selinux/selinux.c')

# ---- kernel_umount.c: path_umount is 5.11+ (4.9 has do_umount with fs-internal struct mount) - no-op on 4.9
_kum = open(os.path.join(BASE, 'kernel_umount.c'), encoding='utf-8', errors='replace').read()
_kum = _kum.replace('''extern int path_umount(struct path *path, int flags);

static void ksu_umount_mnt(struct path *path, int flags)
{
    int err = path_umount(path, flags);
    if (err) {
        pr_info("umount %s failed: %d\\n", path->dentry->d_iname, err);
    }
}

''', '''#if LINUX_VERSION_CODE >= KERNEL_VERSION(5, 11, 0)
extern int path_umount(struct path *path, int flags);
#else
static int ksu_path_umount_49(struct path *path, int flags) { return -EOPNOTSUPP; }
#define path_umount ksu_path_umount_49
#endif

static void ksu_umount_mnt(struct path *path, int flags)
{
    int err = path_umount(path, flags);
    if (err) {
        pr_info("umount %s failed: %d\\n", path->dentry->d_iname, err);
    }
}''')
open(os.path.join(BASE, 'kernel_umount.c'), 'w', encoding='utf-8', newline='\n').write(_kum)
print('patched kernel_umount.c')

# ---- supercalls.c: 4.9 API fallbacks (anon_inode_getfd, inode->i_security, __close_fd)
patch_file('supercalls.c', '''#else
#define getfd_secure anon_inode_getfd_secure
#endif''', '''#elif LINUX_VERSION_CODE >= KERNEL_VERSION(5, 1, 0)
#define getfd_secure anon_inode_getfd_secure
#else
#define getfd_secure(name, fops, priv, flags, cred) anon_inode_getfd(name, fops, priv, flags)
#endif''')
patch_file('supercalls.c', '''    struct inode_security_struct *sec = selinux_inode(wrapper_inode);
    if (sec) {
        sec->sid = ksu_file_sid;
    }''', '''#if LINUX_VERSION_CODE >= KERNEL_VERSION(5, 1, 0)
    struct inode_security_struct *sec = selinux_inode(wrapper_inode);
    if (sec) {
        sec->sid = ksu_file_sid;
    }
#endif''')
patch_file('supercalls.c', '''#else
        ksys_close(fd);
#endif''', '''#else
        __close_fd(current->files, fd);
#endif''')

# ---- selinux/sepolicy.c + rules.c: 5.x+ policydb internals - stub out on 4.9
open(os.path.join(BASE, 'selinux/sepolicy.c'), 'w', encoding='utf-8', newline='\n').write(
'#include <linux/kernel.h>\n#include <linux/errno.h>\n#include <linux/uaccess.h>\n'
'#include "selinux.h"\n'
'int handle_sepolicy(unsigned long arg3, void __user *arg4) { return -EOPNOTSUPP; }\n'
'void apply_kernelsu_rules(void) {}\n')
patch_file('Makefile', 'kernelsu-objs += selinux/rules.o\n', '')

# 4.9 fsnotify_alloc_group takes one arg (no flags) - the code already #if's on 6.0, fine.

if errors:
    print('ERRORS:')
    for e in errors:
        print(' -', e)
    sys.exit(1)
print('fix-ksu-v2-4.9: OK')
