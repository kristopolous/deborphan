#!/usr/bin/env python3
"""Generate sample data for development/testing."""

import json
import random
import math
from datetime import datetime, timedelta, timezone

random.seed(42)

PACKAGES = [
    ("apt", 980, 850000, 5),
    ("dpkg", 950, 840000, 3),
    ("base-files", 400, 830000, 0),
    ("coreutils", 870, 820000, 1),
    ("bash", 920, 810000, 2),
    ("gcc-14", 650, 750000, 8),
    ("libc6", 990, 860000, 0),
    ("libssl3", 800, 800000, 1),
    ("systemd", 750, 700000, 12),
    ("linux-image-amd64", 900, 780000, 5),
    ("perl", 700, 650000, 0),
    ("python3", 850, 770000, 3),
    ("ruby", 300, 300000, 4),
    ("nodejs", 550, 500000, 6),
    ("postgresql-16", 400, 400000, 2),
    ("nginx", 500, 450000, 1),
    ("apache2", 450, 420000, 3),
    ("vim", 700, 600000, 0),
    ("emacs", 350, 250000, 7),
    ("git", 800, 750000, 0),
    ("openssh-server", 880, 790000, 1),
    ("curl", 750, 720000, 0),
    ("wget", 650, 620000, 0),
    ("tar", 600, 580000, 0),
    ("gzip", 550, 550000, 0),
    ("findutils", 400, 380000, 0),
    ("grep", 500, 480000, 0),
    ("sed", 450, 430000, 0),
    ("gawk", 350, 320000, 1),
    ("make", 500, 470000, 0),
    ("cmake", 400, 370000, 2),
    ("meson", 300, 280000, 1),
    ("libc-devtools", 350, 340000, 0),
    ("linux-headers-amd64", 400, 380000, 0),
    ("grub-common", 500, 460000, 3),
    ("grub-pc", 450, 410000, 2),
    ("network-manager", 600, 550000, 8),
    ("firefox", 700, 650000, 0),
    ("chromium", 650, 600000, 1),
    ("thunderbird", 400, 350000, 4),
    ("libreoffice-core", 550, 500000, 6),
    ("gimp", 250, 200000, 3),
    ("inkscape", 200, 150000, 5),
    ("blender", 150, 100000, 2),
    ("steam-installer", 300, 250000, 0),
    ("wine", 200, 180000, 10),
    ("qemu-system-x86", 250, 200000, 7),
    ("docker.io", 500, 450000, 0),
    ("podman", 350, 300000, 2),
    ("lxc", 200, 170000, 4),
    ("ansible", 300, 260000, 1),
    ("terraform", 150, 120000, 0),
    ("awscli", 250, 210000, 3),
    ("sqlite3", 600, 560000, 0),
    ("mariadb-server", 300, 270000, 5),
    ("redis-server", 350, 310000, 0),
    ("memcached", 200, 170000, 1),
    ("elasticsearch", 100, 80000, 15),
    ("libboost-all-dev", 250, 220000, 8),
    ("libopencv-dev", 150, 120000, 12),
    ("libsfml-dev", 80, 60000, 6),
    ("freeglut3-dev", 50, 35000, 3),
    ("libgl1-mesa-dev", 300, 260000, 0),
    ("libvulkan-dev", 120, 90000, 2),
    ("libpulse0", 400, 370000, 0),
    ("libasound2", 350, 320000, 0),
    ("fonts-dejavu-core", 300, 280000, 0),
    ("fonts-liberation", 250, 230000, 0),
    ("xfonts-base", 200, 180000, 0),
    ("xserver-xorg", 400, 360000, 4),
    ("xorg", 350, 310000, 0),
    ("wayland-protocols", 200, 170000, 1),
    ("sway", 80, 55000, 0),
    ("i3-wm", 250, 210000, 0),
    ("openbox", 150, 120000, 2),
    ("fluxbox", 50, 30000, 8),
    ("icewm", 30, 18000, 12),
    ("sawfish", 10, 5000, 45),
    ("pekwm", 15, 8000, 30),
    ("herbstluftwm", 40, 25000, 5),
    ("dwm", 60, 40000, 1),
    ("bspwm", 70, 50000, 0),
    ("awesome", 120, 95000, 3),
    ("jwm", 20, 12000, 20),
    ("fluxbox", 50, 30000, 8),
    ("openbox", 150, 120000, 2),
    ("blackbox", 10, 6000, 60),
    ("windowmaker", 15, 9000, 35),
    ("fvwm", 25, 15000, 25),
    ("afterstep", 5, 2000, 90),
    ("xbill", 2, 1000, 300),
    ("xteddy", 1, 500, 500),
    ("nethack", 5, 3000, 200),
    ("gnome-sudoku", 20, 15000, 45),
    ("gnome-chess", 15, 10000, 60),
    ("gnome-mahjongg", 10, 7000, 80),
    ("aisleriot", 25, 18000, 30),
    ("four-in-a-row", 8, 5000, 50),
    ("glchess", 10, 7000, 120),
    ("phalanx", 3, 1500, 400),
    ("gnuchess", 12, 8000, 15),
    ("freespaceship", 1, 300, 600),
    ("xjig", 1, 200, 800),
    ("xsok", 1, 150, 1000),
]

MAINTAINERS = [
    "Debian QA Group <qa@debian.org>",
    "APT Development Team <deity@lists.debian.org>",
    "DPKG Developers <debian-dpkg@lists.debian.org>",
    "GNU Core Utilities Maintainers <bug-coreutils@gnu.org>",
    "Bash Maintenance <bug-bash@gnu.org>",
    "GCC Packaging Team <gcc@packages.debian.org>",
    "GNU libc maintainers <debian-glibc@lists.debian.org>",
    "OpenSSL Team <openssl-dev@openssl.org>",
    "systemd Packaging Team <pkg-systemd-maint@lists.debian.org>",
    "Linux Kernel Team <debian-kernel@lists.debian.org>",
    "Perl Packaging Team <debian-perl@lists.debian.org>",
    "Python Apps Team <python-apps-team@lists.debian.org>",
    "Unknown <unknown@debian.org>",
]

def gen_date(days_ago):
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()

packages = []
for name, vote, insts, bugs in PACKAGES:
    days = random.randint(1, 800)
    rc_bug_age = random.uniform(10, 1200) if bugs > 0 else None
    packages.append({
        "source": name,
        "vote": vote,
        "insts": insts,
        "days_since_upload": round(days, 1),
        "last_upload_date": gen_date(days),
        "last_upload_version": f"1:{random.randint(1,9)}.{random.randint(0,20)}.{random.randint(0,9)}",
        "rc_bug_count": bugs,
        "oldest_rc_bug_age": round(rc_bug_age, 1) if rc_bug_age else None,
        "maintainer": random.choice(MAINTAINERS),
        "vcs_status": random.choice(["OK", "OK", "OK", "new_commits", "unrep_packaged", None]),
        "vcs_url": f"https://salsa.debian.org/{name}-team/{name}",
    })

output = {
    "fetched_at": datetime.now(timezone.utc).isoformat(),
    "package_count": len(packages),
    "packages": packages,
}

with open("data/packages.json", "w") as f:
    json.dump(output, f, indent=2)

print(f"Wrote {len(packages)} sample packages to data/packages.json")
