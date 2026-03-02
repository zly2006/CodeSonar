# Code Sonar

把你的电脑变成一首正在演奏的曲子。

Code Sonar 实时读取系统传感器数据（CPU、内存、网络），将其映射为生成式环境音乐并持续播放。音乐跟随你的系统状态呼吸——编译时变密，空闲时疏落，网络爆发时闪出高音——但始终保持在舒适、不刺耳的五声音阶内，可以连续开启半小时以上作为背景音。

每一个音符被弹奏时，控制台都会输出它的时间、音色、音高和决策原因。

## 运行

```bash
# 安装依赖（需要 Python 3.11+）
pip install scamp scamp_extensions psutil

# macOS 还需要 FluidSynth 提供 MIDI 合成
brew install fluid-synth

python main.py
```

按 `Ctrl+C` 停止。



## 控制台输出格式

```
──────────── Bar 1 | 4/4 | BPM=62 ────────────
[PAD  ] 11:27:01 | Bar   1 Beat 0 4/4 BPM=  62 | 音色:ElecPiano      音高:['F3', 'C4', 'A4'] 力度:0.30 时值:4.0拍 | 王道进行第1步: IV F大（Bar 1，共4拍） | CPU=15% RAM=54% NET=2%
[BASS ] 11:27:01 | Bar   1 Beat 0 4/4 BPM=  62 | 音色:FretlessBass   音高:C2 (MIDI 36)       力度:0.38 时值:8.0拍 | 根音持续，RAM=54%，横跨2小节(8拍) | CPU=15% RAM=54% NET=2%
[DROP ] 11:27:02 | Bar   1 Beat 1 4/4 BPM=  62 | 音色:Vibraphone     音高:E5 (MIDI 76)       力度:0.23 时值:0.7拍 | CPU活跃(15%)→脉冲点缀 (Beat 1/3, prob=29%) | CPU=15% RAM=54% NET=2%
```



## 架构

```
main.py
└── Conductor
    ├── SystemSensor   (sensors.py)   — 采集 CPU / RAM / NET，滑动平均平滑
    ├── Metronome      (metronome.py) — 共享节拍状态机，唯一时间基准
    └── SCAMP Session  (scamp)        — 多轨 MIDI 合成输出
```

### 传感器 → 音乐参数映射

| 传感器 | 映射目标 | 规则 |
|--|||
| **CPU** | BPM | `50 + CPU × 32`（50~82），每小节平滑 ±2 |
| **CPU** | Vibraphone 音符密度 | 触发概率 `20% + CPU × 60%` |
| **CPU** | Pad 音量 | `0.28 + CPU × 0.18` |
| **RAM** | Bass 音高 | RAM > 80% 时低音下沉四度 |
| **NET** | Vibraphone 音区 | NET > 20% 时按 NET 值概率触发高八度「闪光音」 |

### 节奏设计

- **拍号固定 4/4**，所有声部对齐到同一节拍时钟（`loop_clock`），不会漂移。
- **Beat 0（强拍）** 属于 Pad 换和弦，Vibraphone 在此静默。
- **Beat 1~3（弱拍）** 由 CPU 决定 Vibraphone 是否触发，不与和弦冲突。

### 和声设计

和弦按**王道进行 IV-V-iii-vi**循环，以 C 大调为根音：

| 小节 | 级数 | 和弦 | 音符 |
|||||
| 1    | IV   | F 大 | F3 · C4 · A4 |
| 2    | V    | G 大 | G3 · D4 · B4 |
| 3    | iii  | E 小 | E3 · B3 · G4 |
| 4    | vi   | A 小 | A3 · E4 · C5 |

旋律音（Vibraphone）从 C 大调五声音阶 `[C D E G A]` 中随机取音，与以上四个和弦在音阶上均协和，不会出现不协和音程。

### 三个声部的职责

| 声部 | 乐器 | 时值 | 职责 |
|||||
| **Pad** | Electric Piano | 1 小节（4 拍） | 和弦铺底，建立调性 |
| **Droplets** | Vibraphone | 0.7 拍 | 弱拍点缀，反映 CPU 活跃度 |
| **Bass** | Fretless Bass | 2 小节（8 拍） | 根音持续，RAM 高时下沉 |



## 依赖

| 包 | 用途 |
|-||
| `scamp` | 多轨生成式音乐框架，负责 MIDI 合成与多线程时序 |
| `scamp_extensions` | SCAMP 扩展工具 |
| `psutil` | 跨平台系统传感器（CPU/RAM/NET） |
| `fluid-synth` | MIDI SoundFont 渲染（macOS 通过 Homebrew 安装） |
