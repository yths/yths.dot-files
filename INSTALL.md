# Installation

## Disclaimer

This guide reproduces the yths.dot-files test system, also available as a VM. The goal is a minimal Arch Linux installation with broad hardware support and reasonable privacy defaults. That said, assume this guide can break your system, leak private data, or cause data loss. Proceed only if you understand the risks.

## Prerequisites

Before starting, ensure you have:

* A working computer or VM environment to perform the installation from
* The most recent [Arch Linux ISO](https://archlinux.org/download/) with its verified signature (this guide uses `2026.04.01`, kernel `6.19.10`)
* A USB drive for bare-metal installations
* Network access (wired or wireless)

## Conventions

Throughout this guide, the following placeholders appear. Replace them with values appropriate to your system.

| Placeholder | Description | Example |
|---|---|---|
| `<disk>` | Target disk device path | `/dev/sda`, `/dev/nvme0n1` |
| `<disk-part1>` | Boot partition | `/dev/sda1`, `/dev/nvme0n1p1` |
| `<disk-part2>` | Swap partition | `/dev/sda2`, `/dev/nvme0n1p2` |
| `<disk-part3>` | Root partition | `/dev/sda3`, `/dev/nvme0n1p3` |
| `<user>` | Your username | `yths` |
| `<hostname>` | Machine hostname | `arch` |
| `<time-zone>` | Your time zone | `Europe/Berlin` |
| `<primary-dns>` | Primary DNS server | `1.1.1.1` |
| `<fallback-dns>` | Fallback DNS server | `9.9.9.9` |

SATA disks typically appear as `/dev/sdX`, NVMe drives as `/dev/nvmeXnY` with partitions as `/dev/nvmeXnYpZ`, and VirtIO drives as `/dev/vdX`. Use `lsblk` to identify your target disk.

## Setting Up the Virtual Machine

This section is only required when creating and running the system as a VM with QEMU. Install QEMU and UEFI firmware on the host:

```bash
yay -S qemu-base edk2-ovmf
```

`yay` is an AUR helper installed in the [final step](#installing-the-aur-helper) of this guide. On a fresh host system, use `pacman -S qemu-base` and install `edk2-ovmf` from AUR separately.

Create the disk image:

```bash
qemu-img create -f raw yths-dot-files-base 8G
```

Boot the image with the installation medium:

```bash
qemu-system-x86_64 \
  -cdrom Downloads/archlinux-2026.04.01-x86_64.iso \
  -boot order=d \
  -drive file=yths-dot-files-base,format=raw \
  -enable-kvm \
  -m 8192 \
  -netdev user,id=net0 \
  -device virtio-net-pci,netdev=net0
```

Copy the firmware and make it writable:

```bash
cp /usr/share/edk2/x64/OVMF.4m.fd .
chmod u+w OVMF.4m.fd
```

Boot the image with UEFI-enabled firmware:

```bash
qemu-system-x86_64 \
  -drive file=yths-dot-files-base,format=raw \
  -enable-kvm \
  -m 8192 \
  -netdev user,id=net0 \
  -device virtio-net-pci,netdev=net0 \
  -drive if=pflash,format=raw,file=OVMF.4m.fd
```

## Creating the Installation Medium

Identify your USB drive using `lsblk`, then create an EFI System Partition (type `ef00`) on it using `gdisk`.

> **WARNING:** Verify the device path carefully. Writing to the wrong device will destroy its data.

```bash
mkfs.fat -F 32 /dev/disk/by-id/<usb-drive-partition>
mount /dev/disk/by-id/<usb-drive-partition> /mnt
bsdtar -x -f archlinux-<version>-x86_64.iso -C /mnt
umount /mnt
```

## Preparing the Disk

Boot into the Arch Linux installation system. Adjust your keyboard layout if necessary:

```bash
loadkeys de-latin1
```

Identify the target disk:

```bash
lsblk
```

### Wiping the Disk

The following command fills the entire disk with encrypted zeros, making used space indistinguishable from free space. This protects against cryptographic analysis of the encrypted volume.

> **WARNING:** This irreversibly overwrites all data on `<disk>`.

```bash
dd if=/dev/zero bs=16M | openssl enc -aes-256-ctr -pass pass:x -nosalt | dd of=<disk> bs=16M status=progress oflag=direct
```

### Partitioning

Create partitions using `gdisk <disk>`:

| # | Purpose | Size | Type Code |
|---|---------|------|-----------|
| 1 | EFI System Partition (boot) | 2 GiB | `ef00` |
| 2 | Swap | 8 GiB | `8200` |
| 3 | Root (encrypted) | Remaining space | `8300` |

### Formatting and Encrypting

> **WARNING:** `cryptsetup luksFormat` irreversibly destroys all existing data on the target partition.

```bash
mkfs.fat -F 32 <disk-part1>
mkswap <disk-part2>
cryptsetup luksFormat <disk-part3>
cryptsetup luksOpen <disk-part3> cryptroot
mkfs.btrfs -L root /dev/mapper/cryptroot
```

Create Btrfs subvolumes for root and home:

```bash
mount /dev/mapper/cryptroot /mnt
btrfs subvolume create /mnt/@
btrfs subvolume create /mnt/@home
umount /mnt
```

### Mounting

Mount all partitions. The Btrfs options below enable transparent compression (`zstd:3`), reduce write frequency (`commit=120`), and enable asynchronous TRIM for SSDs (`discard=async`):

```bash
swapon <disk-part2>
mount -o noatime,compress=zstd:3,space_cache=v2,commit=120,discard=async,subvol=@ /dev/mapper/cryptroot /mnt
mkdir -p /mnt/{boot,home}
mount -o noatime,compress=zstd:3,space_cache=v2,commit=120,discard=async,subvol=@home /dev/mapper/cryptroot /mnt/home
mount <disk-part1> /mnt/boot
```

## Configuring the Base System

### Connecting to the Network

For wired connections, `dhcpcd` starts automatically in the live environment. For wireless, use `iwctl`:

```bash
iwctl station wlan0 scan
iwctl station wlan0 get-networks
iwctl station wlan0 connect <network-name>
```

Verify connectivity:

```bash
curl -s --head https://archlinux.org | head -n 1
```

### Setting the Hardware Clock

Synchronize the hardware clock to UTC:

```bash
timedatectl set-ntp true
timedatectl set-local-rtc 0 --adjust-system-clock
hwclock --systohc --utc
timedatectl
```

### Installing the Base Packages

Install the base system. Replace `intel-ucode` with `amd-ucode` if your system has an AMD processor:

```bash
pacstrap -K /mnt base base-devel linux linux-firmware btrfs-progs iwd dhcpcd openssh bluez bluez-utils less vim git intel-ucode
```

Generate the `fstab`:

```bash
genfstab -U /mnt >> /mnt/etc/fstab
```

### Entering the New System

Change root into the installed system. All subsequent commands run inside the chroot:

```bash
arch-chroot /mnt
```

### Configuring the Time Zone

```bash
ln -sf /usr/share/zoneinfo/<time-zone> /etc/localtime
timedatectl set-ntp true
hwclock --systohc
```

### Configuring the Locale

Uncomment your desired locales in `/etc/locale.gen`, then generate them:

```bash
sed -i 's/^#en_US.UTF-8 UTF-8/en_US.UTF-8 UTF-8/' /etc/locale.gen
sed -i 's/^#de_DE.UTF-8 UTF-8/de_DE.UTF-8 UTF-8/' /etc/locale.gen
locale-gen
echo "LANG=en_US.UTF-8" > /etc/locale.conf
```

### Configuring the Virtual Console

Adjust the keymap, layout, and font to your preference:

```bash
cat > /etc/vconsole.conf << 'EOF'
KEYMAP=us
XKBLAYOUT=us
XKBVARIANT=intl
FONT=LatGrkCyr-12x22
EOF
```

### Setting the Hostname

```bash
echo "<hostname>" > /etc/hostname
cat > /etc/hosts << 'EOF'
127.0.0.1 localhost
::1       localhost
127.0.1.1 <hostname>.localdomain <hostname>
EOF
```

### Configuring DNS

Configure `systemd-resolved` as the system DNS resolver:

```bash
cat > /etc/systemd/resolved.conf << 'EOF'
[Resolve]
DNS=<primary-dns>
FallbackDNS=<fallback-dns>
Domains=~.
DNSSEC=no
MulticastDNS=yes
LLMNR=no
EOF
```

Symlink `resolv.conf` to the stub resolver so that applications use `systemd-resolved`:

```bash
ln -sf /run/systemd/resolve/stub-resolv.conf /etc/resolv.conf
```

### Setting the Root Password

```bash
passwd
```

## Configuring the Boot Loader

Install systemd-boot:

```bash
bootctl --esp-path=/boot install
cat > /boot/loader/loader.conf << 'EOF'
default arch.conf
timeout 0
EOF
```

Retrieve the UUID of the encrypted root partition:

```bash
ROOT_UUID=$(blkid -s UUID -o value <disk-part3>)
echo "Root partition UUID: $ROOT_UUID"
```

Create the default boot entry. Replace `intel-ucode.img` with `amd-ucode.img` for AMD systems:

```bash
cat > /boot/loader/entries/arch.conf << EOF
title   Arch Linux
linux   /vmlinuz-linux
initrd  /intel-ucode.img
initrd  /initramfs-linux.img
options rd.luks.uuid=${ROOT_UUID} rd.luks.name=${ROOT_UUID}=cryptroot root=/dev/mapper/cryptroot rootflags=subvol=@ rw quiet loglevel=0 systemd.show_status=auto rd.udev.log_level=0 vt.global_cursor_default=0 video=1920x1080
EOF
```

Create a fallback entry for recovery. This entry omits the silent boot parameters so that full diagnostic output is visible when troubleshooting:

```bash
cat > /boot/loader/entries/arch-fallback.conf << EOF
title   Arch Linux (fallback)
linux   /vmlinuz-linux
initrd  /intel-ucode.img
initrd  /initramfs-linux-fallback.img
options rd.luks.uuid=${ROOT_UUID} rd.luks.name=${ROOT_UUID}=cryptroot root=/dev/mapper/cryptroot rootflags=subvol=@ rw
EOF
```

### Configuring the Initial Ramdisk

Edit `/etc/mkinitcpio.conf`:

* Add `btrfs` to the `MODULES` array. For virtual machine installations, also add the virtio drivers so the kernel can access virtio devices during early boot:
  ```
  MODULES=(btrfs virtio virtio_blk virtio_pci virtio_net)
  ```
  For bare-metal installations, `btrfs` alone is sufficient.
* Replace the default hooks with systemd-based hooks, placing `sd-encrypt` before `filesystems`:
  ```
  HOOKS=(base systemd autodetect microcode modconf kms keyboard sd-vconsole block sd-encrypt filesystems fsck)
  ```

Regenerate the boot images:

```bash
mkinitcpio -P
```

## Finalizing the System

### Initializing the Keyring

```bash
pacman-key --init
pacman-key --populate
```

### Enabling Services

Enable the base set of system services. SSH and Bluetooth are installed but not enabled here; enable them as needed.

```bash
systemctl enable systemd-boot-update.service
systemctl enable systemd-timesyncd.service
systemctl enable systemd-resolved.service
systemctl enable iwd.service
systemctl enable dhcpcd.service
```

### Creating the User

Create a user, add them to the `wheel` group, and set their password:

```bash
useradd -m -G wheel -s /bin/bash <user>
passwd <user>
```

Grant `sudo` access to the `wheel` group:

> **WARNING:** A malformed `/etc/sudoers` locks out `sudo` access. Validate the file after editing.

```bash
sed -i 's/^# %wheel ALL=(ALL:ALL) ALL/%wheel ALL=(ALL:ALL) ALL/' /etc/sudoers
visudo -c
```

### Rebooting

Exit the chroot, unmount all partitions, and reboot:

```bash
exit
umount -R /mnt
reboot
```

## Installing the AUR Helper

Log in as your user and install `yay`:

```bash
git clone https://aur.archlinux.org/yay-bin.git
cd yay-bin
makepkg -si
cd ..
rm -rf yay-bin
```
