**NOTE:** This project is new, the guide is currently quite complicated, and it only works with ChromeOS Widevine 4.10.2557.0

# Xfinity Stream on Linux

Thanks to [TheBrokenRail](https://thebrokenrail.com/2022/12/31/xfinity-stream-on-linux.html), it was shown that the ChromeOS Widevine library could be run on linux and thus allow Xfinity Stream.  This project iterates on that work by patching `GLIBC_ABI_DT_RELR` into the Widevine CDM, negating the need to recompile glibc, and extending support to linux distros not using glibc 2.36+ (such as Ubuntu 22.04).

The technique and modified Widevine CDM have been tested in:

* debian 12 in firefox (native glibc 2.36+)
* ubuntu and PopOS 22.04 using chroot chromium

# How it works

1. Obtain a ChromeOS version of Widevine CDM
2. Patch `GLIBC_ABI_DT_RELR` into Widevine CDM
3. Create a chroot to run glibc 2.36+ Chromium (for systems on glibc <2.36)
4. Replace browser's Widevine CDM with patched version

# (1) Obtain a ChromeOS version of Widevine CDM

These instructions have only been tested with the [ChromeOS `atlas` v107](https://dl.google.com/dl/edgedl/chromeos/recovery/chromeos_15117.112.0_atlas_recovery_stable-channel_mp.bin.zip), the same used by TheBrokenRail, but may be trivially extended to work with [other versions](https://chromiumdash.appspot.com/serving-builds?deviceCategory=Chrome%20OS).

```shell
wget https://dl.google.com/dl/edgedl/chromeos/recovery/chromeos_15117.112.0_atlas_recovery_stable-channel_mp.bin.zip
unzip chromeos_15117.112.0_atlas_recovery_stable-channel_mp.bin.zip
sudo mkdir /mnt/iso
sudo mount -t auto -o ro,loop,offset=683671552 chromeos_15117.112.0_atlas_recovery_stable-channel_mp.bin /mnt/iso
cp /mnt/iso/opt/google/chrome/WidevineCdm/_platform_specific/cros_x64/libwidevinecdm.so ~/
sudo umount /mnt/iso
```

The offset in the mount command is retrieved by running `fdisk -l <image>.bin`, then multiplying sector size (512) by the start sector (1335296) of the largest root FS.  The value may vary if using a different ChromeOS base image.

# (2) Patch `GLIBC_ABI_DT_RELR` into Widevine CDM

The ChromeOS Widevine CDM is compiled with [DT_RELR](https://maskray.me/blog/2021-10-31-relative-relocations-and-relr), but without the GNU ELF dependency, `GLIBC_ABI_DT_RELR`, required by glibc 2.36+.  Fortunately we can patch in the required dependency so the Widevine library can be loaded by glibc.

The included Dockerfile simplifies the patching process.  After cloning the repository, ensure that `libwidevinecdm.so` obtained in step 1 is present at the root of the project, then run:

```shell
make patch-widevine
```

If it succeeds a new file `libwidevinecdm.so.patched` will have been created.  On systems with glibc 2.36+ running `ldd libwidevinecdm.so.patched` will return successfully if patching succeeded.  On systems with glibc <2.36, running `readelf -V libwidevinecdm.so.patched` should reveal the `GLIBC_ABI_DT_RELR` dependency as a child of `libc.so.6`.

The patching process, which is unusually rough due to the immaturity of this project, is outlined below:

1. Install build dependencies needed to compile and execute patching
2. Clone source of `patchelf`
3. Modify `patchelf` to:
   1. Add the `GLIBC_ABI_DT_RELR` string to `.dynstr`
   2. Resize `.gnu.version_r` to make room for new dependency
   3. Update/relocate any section references accordingly
4. Compile `patchelf`
5. Run `patchelf`
6. Run python script to add missing `vernaux` structure

**NOTE:** The python script is using hardcoded offsets and will only work with ChromeOS Widevine CDM 4.10.2557.0

# (3) Create a chroot for Chromium

**NOTE:** This is only required for systems running glibc <2.36!

Both flatpak and snap include their own copy of glibc, but sadly none of the [flatpak runtimes](https://docs.flatpak.org/en/latest/available-runtimes.html) or [base snaps](https://snapcraft.io/docs/base-snaps) yet include glibc 2.36+.  In the near future it is likely that both flatpaks and snaps for popular browsers (firefox/chromium/etc.) will be built using glibc 2.36+ but, until such a time, chrooting is a fine alternative.

Chromium fortunately includes [chroot instructions](https://github.com/chromium/chromium/blob/main/docs/linux/using_a_chroot.md) for development, but the [install script](https://github.com/chromium/chromium/blob/main/build/install-chroot.sh) can be trivially modified to configure a chroot and install the latest release of Chromium.

**NOTE:** The chroot is not optimized and can be quite large, ~1.5GB

The following will download, patch, and then run the chromium chroot tool.  When prompted, select `bookworm` (debian 12) and 64-bit version.

```shell
wget https://raw.githubusercontent.com/chromium/chromium/bba9a08e0e2b1df323d2b290d5afa281fba37374/build/install-chroot.sh
patch < chromium-install-chroot.diff
./install-chroot.sh
```

If the install is successful, attempt to run chromium via the chroot to ensure it works:

```shell
bookworm64 chromium
```

**NOTE:** I had some issues with audio on PopOS so the command I use, which also sets the user-agent, is:

```shell
bookworm64 chromium --alsa-output-device="hw:1,0" --user-agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
```

# (4) Swapping in patched Widevine CDM

The patched Widevine CDM, `libwidevinecdm.so.patched`, created in step 2, needs to be moved to the appropriate place so it can be loaded by your browser (or chroot chromium).

In all cases the user must also change the user agent to a Windows/Mac agent string, or Xfinity Stream will refuse to load.

## For chroot chromium (step 3)

**NOTE:** Files have to be moved into home directory, which is mounted in chroot, so they are accessible

```shell
cp libwidevinecdm.so.patched ~/
wget https://dl.google.com/widevine-cdm/4.10.2557.0-linux-x64.zip
unzip -x libwidevinecdm.so ~/
chmod +r ~/{LICENSE,manifest.json}
sudo bookworm64 mkdir -p /usr/lib/chromium/WidevineCdm/_platform_specific/linux_x64/
sudo bookworm64 cp /home/$(whoami)/libwidevinecdm.so.patched /usr/lib/chromium/WidevineCdm/_platform_specific/linux_x64/libwidevinecdm.so
sudo bookworm64 cp /home/$(whoami)/{LICENSE,manifest.json} /usr/lib/chromium/WidevineCdm/
```

**NOTE:** Any file matching the following also needs to be replaced: `~/.config/chromium/WidevineCdm/*/_platform_specific/linux_x64/libwidevinecdm.so`

## For firefox

Replace `~/.mozilla/firefox/*/gmp-widevinecdm/4.10.2557.0/libwidevinecdm.so` with `libwidevinecdm.so.patched`

## For Vivaldi

Replace `~/.config/vivaldi/WidevineCdm/*/_platform_specific/linux_x64/libwidevinecdm.so` with `libwidevinecdm.so.patched`
