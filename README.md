# MiHome-Windows（custom 版）

米家设备的 Windows 桌面控制端。本仓库是
[huanyuejue/MiHome-Windows](https://github.com/huanyuejue/MiHome-Windows)
的**二次开发分支（fork）**，公开发行名称为 **custom 版**（应用内标题
「米家 - MiHome for Windows（custom 版）」）。在原版功能全部保留的
基础上，针对日常使用体验做了一批界面调整与功能扩展，供自用与交流。

配套的**虚拟测试包 custom-mock**（多种类模拟设备，仅供离线界面测试）
另行发布，不随正式源码分发，两者安装互不影响。

原版：https://github.com/huanyuejue/MiHome-Windows

> **注意：当前项目仍处于早期版本。** 作者个人米家设备有限，无法对各类设备
> 做针对性适配测试，因此 UI 和操作逻辑的完善度不算很高。不过基础使用
> （扫码登录、设备列表与常用控制、托盘、小组件、小爱语音等）已无大碍，
> 需适配更多设备功能则依赖社区支持。

## 下载（Releases）

| 版本 | 说明 | 附件下载 |
|------|------|----------|
| **custom 版 v0.2.1（正式版）** — [Releases](https://github.com/iop666/MiHome-Windows/releases/tag/v0.2.1) | 含便携版 + 安装版 | [MiHome-Windows-custom-0.2.1-portable.zip](https://github.com/iop666/MiHome-Windows/releases/download/v0.2.1/MiHome-Windows-custom-0.2.1-portable.zip) ／ [MiHome-Windows-custom-0.2.1-setup.exe](https://github.com/iop666/MiHome-Windows/releases/download/v0.2.1/MiHome-Windows-custom-0.2.1-setup.exe) |
| **custom-mock 0.2.1（模拟设备测试版）** — [Releases](https://github.com/iop666/MiHome-Windows/releases/tag/mock-0.2.1) | 264 台 / 66 小类虚拟家庭，完全离线 | [MiHome-Windows-custom-mock-0.2.1-portable.zip](https://github.com/iop666/MiHome-Windows/releases/download/mock-0.2.1/MiHome-Windows-custom-mock-0.2.1-portable.zip) |

## 关于本分支

本分支（fork）的**开发与发布过程均由 DeepSeek Harness 协助完成**。

## custom 版主要更新

- **设备卡片右键拖拽排序**：动画让位、边缘自动滚动，顺序持久化保存；
- **排序管理**：设置页新增「撤销 / 恢复卡片移动」「恢复默认排序」；
- **设备重命名**：详情页可重命名设备并恢复默认名，桌面小组件 / 托盘 /
  主界面实时同步，名称过长自动换行；
- **数值单位与中文标题**：详情页属性补全单位（亮度 %、色温 K、温度 °C、
  湿度 %、功率 W 等），属性标题与枚举选项尽量中文化；
- **多配色主题**：内置 6 种强调色（绿 / 蓝 / 紫 / 橙 / 玫红 / 青），切换时
  开关、按钮等控件同步换色；
- **桌面小组件**：名称随主界面重命名实时同步。

## 与原版的差异

本 fork 在原版基础上做了以下修改与新增（以提交记录为准，按功能归类）：

### 主界面与设备卡片

|示例1|示例2|示例3|
|---|---|---|
| <img width="288" height="180" alt="2026-09-04 01-15-39" src="https://github.com/user-attachments/assets/0cb051c7-4a42-45bb-a0e9-27b97f463f34" /> | <img width="288" height="180" alt="2026-09-04 01-15-39_1" src="https://github.com/user-attachments/assets/7a7f2ec0-1ec3-4ba1-8e77-72998f952705" /> | <img width="288" height="180" alt="2026-09-04 01-15-39_2" src="https://github.com/user-attachments/assets/ae1c97f4-64e3-4839-b4d0-48dfd889b9c9" /> |

- 设备卡片**右键拖拽排序**：拖动时其余卡片动画让位、窗口边缘自动滚动，
  松开即落位，顺序写入用户数据目录；设置页可撤销/恢复每次移动，也可一键
  恢复默认排序（家庭/房间分组由云端决定）；
- 卡片显示产品图与在线状态，支持隐藏无功能设备、快捷操作弹层等。

### 设备详情页（工作台）

| 示例 |
| :---: |
| <img width="600" height="172" alt="image" src="https://github.com/user-attachments/assets/37ba6130-5521-422b-b040-c6b6ac490bf1" /> |
| <img width="600" height="232" alt="image" src="https://github.com/user-attachments/assets/8f935c76-afcc-413d-bd22-fc27e9f275e1" /> |

- 属性项数值补全单位后缀（亮度 `%`、色温 `K`、温度 `°C`、湿度 `%`、
  功率 `W` 等，无法确定的单位不加）；
- 属性标题中文化（型号无关的中文回退），枚举选项尽量显示中文；
- 详情页头部新增**重命名**与**恢复默认名**按钮，改名后主界面网格、
  系统托盘与桌面小组件即时同步；
- 保留原版的开关 / 滑块 / 下拉 / 动作执行 / 快捷操作 / 智能默认 /
  米家场景与真机安全保护。

### 主题与外观

- **6 种强调色可选**（绿 / 蓝 / 紫 / 橙 / 玫红 / 青）：调整强调色时，
  开关、按钮、进度条等控件配色即时跟随；

### 桌面小组件

| 示例 |
| :---: |
| <img width="600" height="719" alt="image" src="https://github.com/user-attachments/assets/9e20051b-ddfd-434b-bdf1-34395bdb564f" /> |

- 把单个或多个设备「固定到桌面」的常驻小组件：只显示设备控件、无标题栏；
- 多设备可合并在一个小组件里，每台设备可**自选展开哪些调节控件**（亮度/
  色温/模式等），全部不选则只留开关行；
- 小组件可单独固定**浅色 / 深色外观**（或跟随应用主题），也可随时
  **隐藏/显示**（隐藏不删除配置）；
- 支持 1% 步进缩放、锁定/解锁、置顶、背景透明度（0% 时边框也跟随消失）；
- 开关状态与调节值随主窗口/托盘/详情页**实时同步**，并周期回读云端真实值。

### 系统托盘

| 示例1 | 示例2 |
| :---: | :---: |
| <img width="446" height="640" alt="image" src="https://github.com/user-attachments/assets/d295f909-bacb-4349-aa1a-48cff98be58e" /> | <img width="382" height="640" alt="image" src="https://github.com/user-attachments/assets/87ca2777-24de-4312-a222-f550d912ef10" /> |

- 托盘快捷窗口的单列/双列卡片切换**沿用原版**；本版调整：双列网格下隐藏
  行内「调节」按钮（需要调节时切到单列再展开），并修复托盘重建时新旧行
  残留重叠、窗口高度/贴任务栏等布局问题；
- 「托盘设备常显调节」可选：开启后设备行直接常显调节项（默认关闭，开启会
  隐藏单/双列切换钮）；
- 托盘展开行内的调节值、开关状态与主界面/详情页/桌面小组件**跨界面实时
  同步**；
- 托盘图标颜色可选（白色默认 / 黑色 / 品牌绿），切换即时生效；
- 托盘右键菜单新增「重启应用」。

### 原版功能

扫码登录、家庭/房间分组的设备列表、按 spec 自动生成的详情工作台（开关/
滑块/下拉/动作执行）、快捷操作、米家场景、小爱语音悬浮球与音频快捷控制、
深浅色主题、50%–200% 界面缩放、开机自启动、GitHub Releases 新版本检测、
本地数据缓存等。

## 功能一览（本版）

- **扫码登录**：米家 APP 扫二维码，登录凭据与上游依赖的 CLI 共用
- **设备列表**：按家庭、房间分组，实时显示在线状态，支持隐藏无功能设备
- **设备控制**：根据设备 spec 元数据自动生成控件——布尔属性映射开关、数值
  属性映射滑块（自动套用范围与步长）、枚举属性映射下拉框
- **动作执行**：设备支持的动作渲染为按钮，执行前二次确认（参数化动作可填参）
- **卡片排序**：右键拖拽调整顺序并记忆；可撤销/恢复、恢复默认
- **设备重命名**：详情页改名/恢复默认名，主界面、托盘、小组件同步
- **系统托盘**：最小化到托盘，快捷开关 + 行内调节、小爱音响快捷控制、
  单列/双列切换、常显调节可选
- **桌面小组件**：设备控件常驻桌面，自选控件、单独明暗外观、隐藏/显示
- **主题配色**：深色 / 浅色 / 跟随系统 + 6 种强调色，控件配色即时跟随；
  小组件可单独固定明暗
- **界面缩放**：50%–200% 无级调节（叠加在系统缩放之上），需重启生效
- **开机自启动**：可选，写入当前用户注册表（HKCU Run）
- **小爱语音**：主界面右下角悬浮按钮 / 托盘语音条，文字指令发送给在线
  小爱音箱，可指定默认输出音箱
- **版本检测**：启动时检查上游 GitHub Releases 新版本，也可在关于页手动检测
- **本地缓存**：设置、托盘/小组件/工作台配置与设备缓存存放于用户数据目录
  （见下方路径说明）
- **上游可升级**：mijiaAPI 仅作为 PyPI 依赖锁定在 `>=4.2,<5`，升级后需
  人工验证兼容性再放行

## 运行

要求 Python >= 3.10

### 一键运行

```powershell
git clone https://github.com/iop666/MiHome-Windows.git
cd MiHome-Windows

# 双击 start.bat，或命令行执行：
start.bat
```

`start.bat` 自动完成：创建 venv → 安装依赖 → 启动程序，无需手动配置环境。

### 手动运行

```powershell
git clone https://github.com/iop666/MiHome-Windows.git
cd MiHome-Windows

python -m venv .venv
.venv\Scripts\pip install -e .
.venv\Scripts\python.exe run.py
```

首次启动会弹出扫码窗口；之后凭据长期复用，失效时再次扫码即可。

## 本地缓存与数据存储

程序运行时会在以下位置生成配置和缓存文件，方便用户备份或排查问题。
这些文件**不属于源码**（正式源码与发布包内均不包含）。

### 应用数据（Releases版）

路径：`%LOCALAPPDATA%\MiHome-Windows\`

| 文件 | 说明 |
|------|------|
| `settings.json` | 应用设置（主题、强调色、缩放、托盘、自启动等） |
| `tray.json` | 托盘快捷控制面板的设备列表配置 |
| `tray_ops.json` | 托盘每台设备行内展开的调节项自选 |
| `workbench.json` | 工作台（设备详情页）的自定义布局 |
| `device_names.json` | 设备重命名记录（did -> 自定义名 / 默认名，可一键恢复） |
| `widgets.json` | 桌面小组件配置（设备、位置、缩放、外观等） |
| `devices_cache.json` | 设备列表与状态缓存，启动时优先从缓存加载以加快首屏显示 |
| `.icons/` | 设备产品图缓存（按型号命名，联网拉取一次后本地复用） |

> 路径中的 `%LOCALAPPDATA%` 通常为 `C:\Users\<用户名>\AppData\Local`。
> 旧版曾写在 exe 同目录，首次启动会自动迁移至此。

### 应用数据（源码模式）

路径：项目根目录（与 `run.py` 同级），文件名与 Releases 版一致。

### 米家账号登录凭据

路径：`~/.config/mijia-api/auth.json`

这是 mijiaAPI 的认证文件，扫码登录后长期复用。失效时程序会自动提示重新扫码。

> 路径中的 `~` 在 Windows 上为 `C:\Users\<用户名>`。
> 登录凭据只保存在你自己的用户目录，绝不进入源码或发布包。

## 构建可执行文件

项目使用 **[Nuitka](https://nuitka.net/)** 将 Python 源码编译打包为原生
Windows 可执行文件（standalone 模式：把 Python 解释器、全部依赖与资源文件
整合进一个免安装目录）。Nuitka 是真编译器——把代码编译为 C 再编译为机器码，
因此需要 VS Build Tools。

### 前置条件

| 工具 | 版本 | 说明 |
|------|------|------|
| Python | >= 3.10 | 需加入系统 PATH，构建脚本会自动创建 venv |
| VS Build Tools | 2022 | Nuitka 编译所需的 C 编译器，约 2 GB |

下载安装 VS Build Tools 2022：https://visualstudio.microsoft.com/downloads/#build-tools-for-visual-studio-2022

安装时勾选 **"使用 C++ 的桌面开发"** 工作负载。

### 一键构建

```powershell
git clone https://github.com/iop666/MiHome-Windows.git
cd MiHome-Windows

# 双击 build_msvc.bat 或运行：
.\build.ps1
```

脚本自动完成：创建 venv → 安装依赖（含 Nuitka 本体）→ 激活 MSVC 编译环境 →
Nuitka 编译。standalone 产物（`MiHome-Windows.exe` 及其依赖目录）输出在
`dist` 下，可整体打包为便携版；再配合 Inno Setup 可生成安装版。

首次构建耗时较长（创建 venv + 下载依赖 + Nuitka 编译，通常 10–20 分钟，视机器而定）。

## 项目结构

```
app/
├── core/                       # 核心层
│   ├── service.py              # mijiaAPI 适配层，全项目唯一 import mijiaAPI 的模块
│   ├── mock_devices.py         # 虚拟测试设备源（MIWU_MOCK_DEVICES，仅供离线测试）
│   ├── jobs.py                 # 串行任务队列，所有米家网络调用的后台通道
│   ├── models.py               # 数据模型
│   ├── _json_store.py          # JSON 持久化公共基础（数据目录/迁移/原子写）
│   ├── cache.py                # 设备缓存
│   ├── device_names.py         # 设备重命名记录持久化（did -> 自定义名）
│   ├── settings_store.py       # 应用设置持久化（含开机自启动注册表）
│   ├── tray_store.py           # 托盘配置持久化
│   ├── tray_ops_store.py       # 托盘行内调节项自选持久化
│   ├── widget_store.py         # 桌面小组件配置持久化
│   ├── workbench_store.py      # 工作台配置持久化
│   ├── icons.py                # 设备产品图磁盘缓存
│   ├── safety.py               # 安全模式（MIWU_SAFE_DEVICE）守卫
│   ├── update_checker.py       # GitHub Releases 新版本检查（后台线程 + 信号）
│   └── restart.py              # 应用自重启（缩放等设置需重启生效时一键重启）
├── ui/                         # 界面层
│   ├── main_window.py          # 主窗口（无边框标题栏）
│   ├── device_grid.py          # 设备卡片网格（动画让位、右键拖拽排序）
│   ├── tray/                   # 系统托盘
│   │   ├── quick_window.py     #   快捷控制面板（单列/双列、常显、行内调节）
│   │   ├── audio_bar.py        #   音响控制栏
│   │   ├── controller.py       #   托盘控制器（图标配色、右键菜单含重启）
│   │   └── manager_dialog.py   #   托盘设备管理对话框
│   ├── desktop_widget.py       # 桌面小组件窗口（无标题栏、独立明暗外观）
│   ├── widget_manager.py       # 小组件实例管理（增删改查/同步/显隐）
│   ├── widget_dialogs.py       # 小组件设备选择 / 控件自选对话框
│   ├── quick_ops.py            # 快捷调节弹层组件（卡片/托盘行/小组件复用）
│   ├── device_card.py          # 设备卡片组件（产品图、开关）
│   ├── device_dialog.py        # 设备详情对话框
│   ├── workbench_panel.py      # 工作台面板（属性/动作）
│   ├── workbench_item.py       # 工作台属性/动作项
│   ├── prop_widgets.py         # 属性控件（开关、滑块、下拉框）
│   ├── power_button.py         # 三态电源按钮（卡片/托盘/详情共用）
│   ├── overlay_dialog.py       # 遮罩对话框基类（详情/设置/抽屉共用）
│   ├── about_dialog.py         # 关于对话框（custom 版说明、上游致谢、检测更新）
│   ├── settings_dialog.py      # 设置对话框（主题外观/托盘设置/应用功能/小组件）
│   ├── voice_fab.py            # 语音悬浮球
│   ├── toast.py                # 轻量通知浮层
│   ├── update_flow.py          # 版本检查界面流程（弹框提示/静默反馈）
│   ├── login_dialog.py         # 扫码登录对话框
│   ├── add_drawer.py           # 设备添加抽屉
│   ├── typewriter.py           # 打字机效果组件
│   ├── si_theme.py             # 主题中枢（明暗调色板 + 强调色 + 全局 QSS）
│   ├── theme_service.py        # 主题编排（跟随系统/浅色/深色）
│   ├── restart.py              # 应用自重启
│   ├── icon.ico / icon.png     # 应用图标
│   └── tray_icon*.png          # 托盘图标（白/黑/品牌绿）
├── siui/                       # 内置 SiliconUI 组件库（GPL-3.0）
│   ├── components/             # UI 组件
│   ├── core/                   # 核心工具
│   └── gui/                    # 图形工具
└── __init__.py                 # 版本号 + 工具函数

run.py                          # 程序入口
start.bat                       # Windows 一键运行（双击运行）
build_msvc.bat                  # Windows 一键构建（双击运行，转发 build.ps1）
build.ps1                       # PowerShell 构建脚本（Nuitka 参数集中维护）
pyproject.toml                  # 项目配置
LICENSE                         # GPL-3.0 许可证
```

## 依赖说明

| 包名 | 版本 | 用途 |
|------|------|------|
| mijiaAPI | >=4.2,<5 | 米家 API 封装 |
| PySide6 | >=6.7 | Qt6 绑定 |
| qrcode | >=8 | 登录二维码生成 |
| qtawesome | >=1.4 | Material Design 图标 |
| numpy | - | SiliconUI 动画插值 |
| typing_extensions | - | SiliconUI 在 Python 3.10 下所需的类型别名 |

## 开源许可

本项目基于 [GPL-3.0](LICENSE) 或更高版本发布，允许在遵守协议的前提下自由
使用、修改与再分发。

### 上游与第三方组件

- [huanyuejue/MiHome-Windows](https://github.com/huanyuejue/MiHome-Windows)
  - 本 fork 的原版项目，界面与交互的大部分实现来源于此，向原作者致谢
- [mijia-api](https://github.com/Do1e/mijia-api) - 米家 API 封装
- [PySide6-SiliconUI](https://github.com/H1DDENADM1N/PySide6-SiliconUI) -
  UI 组件库（已内置至 `app/siui/`）

对本项目代码的使用、修改与分发同样须遵循 GPL-3.0。

本程序不含任何担保。请自行承担使用风险，并遵守小米的服务条款。

## 相关仓库

- [iop666/mijia-product-icons](https://github.com/iop666/mijia-product-icons) —— 米家产品**示例样图库**：17 大类 / 10,000+ 产品型号的设备示例样图与对照清单，可查看各型号设备的样图。
