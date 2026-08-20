# AnyKernel3 Ramdisk Mod Script
# osm0sis @ xda-developers
## AnyKernel setup
# begin properties
properties() { '
kernel.string=Gravity_Ext KernelSU+SUSFS for Sony Xperia XZ2 / XZ2 Compact (tama)
do.devicecheck=1
do.modules=0
do.systemless=1
do.cleanup=1
do.cleanuponabort=0
device.name1=akari
device.name2=xz2
device.name3=apollo
device.name4=xz2c
supported.versions=10 - 15
supported.patchlevels=2019-01 - 2026-12
'; } # end properties

# shell variables
block=/dev/block/bootdevice/by-name/boot;
is_slot_device=auto;
ramdisk_compression=auto;

## AnyKernel methods (DO NOT CHANGE)
. tools/ak3-core.sh;

## AnyKernel file attributes
chmod -R 750 $RAMDISK/*;
chown -R root:root $RAMDISK/*;

## AnyKernel install
dump_boot;

## end install
