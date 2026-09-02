# SPDX-License-Identifier: GPL-3.0-or-later
# MiHome-Windows: 米家设备的 Windows 桌面控制端
# Copyright (C) 2026 MiHome-Windows contributors
"""设备产品图本地缓存（.icons/<model>.png，数据目录下）。

图片来自 home.miot-spec.com 产品页的 product.icon（米家 CDN
iotweb-product-center，与 home.mi.com 百科同源）；仅按需异步拉取，
失败/无图静默跳过，绝不阻塞主流程。
"""

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap

from app.core import _json_store


def cache_dir() -> Path:
    return _json_store.data_dir() / ".icons"


def cache_path(model: str) -> Path:
    safe = model.replace("/", "_").replace("\\", "_").replace(":", "_")
    return cache_dir() / f"{safe}.png"


def load_pixmap(model: str, size: int = 0) -> QPixmap | None:
    """读取缓存 PNG；size>0 时缩放裁切为正方形。"""
    path = cache_path(model)
    if not path.exists():
        return None
    pix = QPixmap(str(path))
    if pix.isNull():
        return None
    if size and size != pix.width():
        pix = pix.scaled(size, size, Qt.KeepAspectRatioByExpanding,
                         Qt.SmoothTransformation)
        pix = pix.copy((pix.width() - size) // 2,
                       (pix.height() - size) // 2, size, size)
    return pix


def save_bytes(model: str, data: bytes) -> bool:
    try:
        path = cache_path(model)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return True
    except OSError:
        return False
