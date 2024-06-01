# yths dot files
## Description

## Installation
### Creating Installation Medium (USB Drive)
Create a primary partition on the USB drive (partition type ef02) with `gdisk`. Format the partition to FAT32 and extract the Arch Linux ISO to this parition:
```
mkfs.fat -F 32 /dev/disk/by-id/{usb-drive-partition}
mount /dev/disk/by-id/{usb-drive-partition} /mnt
bsdtar -x -f archlinux-{version}-x86_64.iso -C /mnt
umount /mnt
```
Boot into the most recent Arch Linux ISO and set the correct keyboard layout:
```
loadkeys de
```
Wipe relevant volumes by overwriting with random data:
```
dd if=/dev/urandom of=/dev/nvme0n1 bs=512 status=progress
```
Initialize partition table (512MB EFI (ef00), 16GB swap (8200), rest root (8300)):
```
gdisk /dev/nvme0n1
```
Create and configure (encrypted) filesystems:
```
mkfs.fat -F32 /dev/nvme0n1p1
mkswap /dev/nvme0n1p2
swapon /dev/nvme0n1p2
cryptsetup luksFormat /dev/nvme0n1p3
cryptsetup luksOpen /dev/nvme0n1p3 cryptroot
mkfs.btrfs /dev/mapper/cryptroot
mount /dev/mapper/cryptroot /mnt
cd /mnt
btrfs subvolume create @
btrfs subvolume create @home
cd
umount /mnt
mount -o noatime,space_cache=v2,compress=zstd,ssd,discard=async,subvol=@ /dev/mapper/cryptroot /mnt
mkdir /mnt/{boot,home}
mount -o noatime,space_cache=v2,compress=zstd,ssd,discard=async,subvol=@home /dev/mapper/cryptroot /mnt/home
mount /dev/nvme0n1p1 /mnt/boot
lsblk
```
Connect to the internet, e.g., by following the official [guide](https://wiki.archlinux.org/title/iwd).
Install base packages:
```
pacstrap /mnt base base-devel linux linux-firmware btrfs-progs wget vim git intel-ucode openssh iwd dhcpcd bluez bluez-utils pacman-contrib
```
Generate fstab:
```
genfstab -U /mnt >> /mnt/etc/fstab
```
Chroot into the new system, download, modify and execute the installation script:
```
arch-chroot /mnt
wget https://raw.githubusercontent.com/yths/yths.dot-files/main/scripts/arch-install-base.sh
chmod +x arch-install-base.sh
./arch-install-base.sh
```
Configure mkinitcpio by adding `btrfs` to the MODULES array and `encrypt` to the HOOKS array (before `filesystems`):
```
vim /etc/mkinitcpio.conf
mkincpio -p linux
```
Configure the bootloader `/boot/loader/loader.conf` and create the following boot entry (replace the microcode image according to your architecture); use `blkid` to get the relevant UUIDs:
```
vim /boot/loader/entries/arch.conf
```
```
title Arch Linux
linux /vmlinuz-linux
initrd /intel-ucode.img
initrd /initramfs-linux.img
options cryptdevice=UUID=<UUID>:root root=UUID=<MAPPER-UUID> rootflags=subvol=@ rw video=3840x2160
```
If desired, create also a fallback boot entry. Reboot the system and rejoice.
## Configuration
Install `yay`:
```
mkdir repositories
git clone https://aur.archlinux.org/yay.git
cd yay
makepkg -si
```
Encrypt swap by following the official [guide](https://wiki.archlinux.org/title/Dm-crypt/Swap_encryption).

### Window Manager
To install [qtile](https://www.qtile.org/) install the following packages:
```
yay -S xorg-server xorg-xinit xorg-xset xorg-xrandr qtile feh python-dbus-next python-grequests ttf-liberation-mono-nerd python-screeninfo
```
Do not forget to symlink `~/.xinitrc` and `~/.confg/qtile` to their respective counterparts in this repository.
### Display Manager
```
yay -S lightdm lightdm-gtk-greeter
```
### Dedicated Graphics Card (optional)
```
yay -S nvidia optimus-manager
```
Do not forget to create the pacman hook as described [here](https://wiki.archlinux.org/title/NVIDIA#pacman_hook).
### Shell and Terminal Emulator
```
yay -S kitty
```
### Window Switcher
```
yay -S rofi
```
### Notification Daemon
```
yay -S dunst
```
## Bug Fixes
### Bluetooth Headset Does Not Connect
Restart wireplumber service:
```systemctl --user restart wireplumber.service```
## Acknowledgements
The initial version of this script is heavily inspired by [eflinux](https://gitlab.com/eflinux/arch-basic).
