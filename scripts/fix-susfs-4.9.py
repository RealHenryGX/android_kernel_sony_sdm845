#!/usr/bin/env python3
# Fix SUSFS kernel-4.9 patch hunks that drift on LineageOS 4.9.227 baseline.
# Run from kernel source root (GITHUB_WORKSPACE) after applying 10_/50_ patches.

import os

def patch_include():
    p = 'fs/proc/task_mmu.c'
    s = open(p, encoding='utf-8').read()
    inc = '#ifdef CONFIG_KSU_SUSFS_SUS_KSTAT\n#include <linux/susfs_def.h>\n#endif\n'
    if 'linux/susfs_def.h' in s:
        print('skip', p, '(already has susfs_def.h)')
        return
    marker = '#include <linux/mm_inline.h>\n'
    assert marker in s, 'mm_inline.h marker not found in ' + p
    s = s.replace(marker, marker + inc, 1)
    open(p, 'w', encoding='utf-8').write(s)
    print('patched', p)

def patch_selinux():
    p = 'KernelSU/kernel/selinux/selinux.c'
    s = open(p, encoding='utf-8').read()
    if 'susfs_set_zygote_sid' in s:
        print('skip', p, '(already has susfs helpers)')
        return
    block = (
        '#ifdef CONFIG_KSU_SUSFS\n'
        'static inline void susfs_set_sid(const char *secctx_name, u32 *out_sid)\n'
        '{\n'
        '\tint err;\n'
        '\t\n'
        '\tif (!secctx_name || !out_sid) {\n'
        '\t\tpr_err("secctx_name || out_sid is NULL\\n");\n'
        '\t\treturn;\n'
        '\t}\n'
        '\n'
        '\terr = security_secctx_to_secid(secctx_name, strlen(secctx_name),\n'
        '\t\t\t\t\t   out_sid);\n'
        '\tif (err) {\n'
        '\t\tpr_err("failed setting sid for \'%s\', err: %d\\n", secctx_name, err);\n'
        '\t\treturn;\n'
        '\t}\n'
        '\tpr_info("sid \'%u\' is set for secctx_name \'%s\'\\n", *out_sid, secctx_name);\n'
        '}\n'
        '\n'
        'bool susfs_is_sid_equal(void *sec, u32 sid2) {\n'
        '\tstruct task_security_struct *tsec = (struct task_security_struct *)sec;\n'
        '\tif (!tsec) {\n'
        '\t\treturn false;\n'
        '\t}\n'
        '\treturn tsec->sid == sid2;\n'
        '}\n'
        '\n'
        'u32 susfs_get_sid_from_name(const char *secctx_name)\n'
        '{\n'
        '\tu32 out_sid = 0;\n'
        '\tint err;\n'
        '\t\n'
        '\tif (!secctx_name) {\n'
        '\t\tpr_err("secctx_name is NULL\\n");\n'
        '\t\treturn 0;\n'
        '\t}\n'
        '\terr = security_secctx_to_secid(secctx_name, strlen(secctx_name),\n'
        '\t\t\t\t\t   &out_sid);\n'
        '\tif (err) {\n'
        '\t\tpr_err("failed getting sid from secctx_name: %s, err: %d\\n", secctx_name, err);\n'
        '\t\treturn 0;\n'
        '\t}\n'
        '\treturn out_sid;\n'
        '}\n'
        '\n'
        'u32 susfs_get_current_sid(void) {\n'
        '\treturn current_sid();\n'
        '}\n'
        '\n'
        'void susfs_set_zygote_sid(void)\n'
        '{\n'
        '\tsusfs_set_sid(KERNEL_ZYGOTE_DOMAIN, &susfs_zygote_sid);\n'
        '}\n'
        '\n'
        'bool susfs_is_current_zygote_domain(void) {\n'
        '\treturn unlikely(current_sid() == susfs_zygote_sid);\n'
        '}\n'
        '\n'
        'void susfs_set_ksu_sid(void)\n'
        '{\n'
        '\tsusfs_set_sid(KERNEL_SU_DOMAIN, &susfs_ksu_sid);\n'
        '}\n'
        '\n'
        'bool susfs_is_current_ksu_domain(void) {\n'
        '\treturn unlikely(current_sid() == susfs_ksu_sid);\n'
        '}\n'
        '\n'
        'void susfs_set_init_sid(void)\n'
        '{\n'
        '\tsusfs_set_sid(KERNEL_INIT_DOMAIN, &susfs_init_sid);\n'
        '}\n'
        '\n'
        'bool susfs_is_current_init_domain(void) {\n'
        '\treturn unlikely(current_sid() == susfs_init_sid);\n'
        '}\n'
        '#endif\n'
        '\n'
    )
    marker = '#define DEVPTS_DOMAIN'
    assert marker in s, 'DEVPTS_DOMAIN marker not found in ' + p
    s = s.replace(marker, block + marker, 1)
    open(p, 'w', encoding='utf-8').write(s)
    print('patched', p)

if __name__ == '__main__':
    assert os.path.isdir('fs') and os.path.isdir('KernelSU'), 'run from kernel source root'
    patch_include()
    patch_selinux()
    print('fix-susfs-4.9 done')
