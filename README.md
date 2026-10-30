# FWID：让 MCU 里的固件可追溯到源码

> **一句话**：每次构建生成一个明文 ID 嵌入镜像，同时把产生该镜像的源码快照按 ID 存档；以后从设备读出 ID，就能找回当时那份代码。

**English:** FWID is a lightweight convention that links a flashed MCU firmware image to the exact source snapshot that produced it. Each build embeds a plaintext build ID and archives its source snapshot under that ID, so the code can be retrieved later from the device.

## 问题

- 设备在手上，但不知道里面烧的是哪一版代码。
- 即使开发者愿意共享，也不知道该给哪一版；生产/销售记录常常缺失或不可靠。
- 二进制反推源码不可行：宏、注释、优化、生成文件都已丢失。
- 手写版本号、`__DATE__` 无法唯一对应构建输入。

## 方法

1. **构建时**：快照构建输入（含未跟踪文件、依赖锁文件、构建配置）→ 生成明文 ID → 嵌入镜像 → 构建并校验 ID 确实在镜像中 → 按 ID 存档快照和元数据 → 上传成功后才允许发布或烧录。
2. **设备上**：开机打印 ID，提供查询命令。ID 保持明文，串口、屏幕、二维码、标签都能承载。
3. **找回时**：从设备读出 ID → 按 ID 取回快照 → 还原出可编译的项目。

## 核心不变式

> **没有成功存档，就不存在可烧录镜像。**

只要所有可能进入设备的镜像都来自“存档成功的构建”，从设备读出的 ID 就必然能解析到对应源码。旧版本包、售后降级、手工选择镜像都不破坏这一点——它们各自带着自己的 ID。

## 为什么用明文 ID

- 不需要密钥管理，不需要 MCU 有密码学外设。
- 任何通道都能读：串口、LCD、二维码、标签、人工抄写。
- ID 本身不是秘密；需要保护的是源码访问，不是 ID。
- 签名/安全启动是可选上层，不改变 ID 的生成和查询方式。

## 仓库内容

| 文件 | 内容 |
| --- | --- |
| [`SPEC.md`](SPEC.md) | 规范主文档（规范性要求、ID 格式、构建记录、存档 profile、一致性等级） |
| [`schema/build-record.schema.json`](schema/build-record.schema.json) | 构建记录的 JSON Schema |
| [`examples/record.example.json`](examples/record.example.json) | 构建记录示例 |
| [`examples/stc8g1k08a/`](examples/stc8g1k08a/) | STC8G1K08A 端到端示例：串口输出 FWID、构建校验、源码存档与取回，含上板实测截图 |
| [`SKILL.md`](SKILL.md) | Claude Code skill，供 AI agent 按规范接入项目 |
| [`LICENSE`](LICENSE) | MIT |

## 快速示例

设备启动输出：

```
FWID:D3M07Q3M9X2KY5
```

构建记录节选：

```json
{
  "spec_version": "0.1.0",
  "fwid": "FWID:D3M07Q3M9X2KY5",
  "project": { "name": "demo-blink", "version": "1.4.2" },
  "source": {
    "snapshot_sha256": "<64 hex>",
    "bundle": "source.tar.zst"
  },
  "image": {
    "file": "demo-blink.bin",
    "sha256": "<64 hex>",
    "format": "bin"
  }
}
```

## 一致性

| Profile | 要求 |
| --- | --- |
| **Core** | 生产者、存档、设备满足 SPEC 第 5–8 章的 MUST；构建记录通过 Schema 校验 |
| **Production** | Core + 烧录同一产物 + read-after-write + 产线 UID ↔ FWID 日志 + 保留策略 + 敏感信息扫描 + 审计 |

## 适用与不适用

**适用**：个人开发者的项目归档与换机找回；团队/企业的交接、售后、审计和长期维护；AI 辅助开发中“构建 → 存档 → 烧录 → 找回”的自动化闭环。

**不适用**：从二进制恢复源码；防伪、防克隆、固件加密或安全启动；设备唯一身份；替代版本控制或构建系统。

## 状态与贡献

这是一个想法/规范草案（0.1.0），附带一个 STC8G1K08A 的最小参考示例（已在 Keil C51 9.61 上编译通过，并在 STC8G1K08A-8PIN 上烧录验证）。欢迎 issue/PR 讨论、补充实现或指出漏洞。

采用 MIT License。

## 与 AI agent 配合

把本仓库放进 `.claude/skills/firmware-build-id/`（个人）或项目的 `.claude/skills/`，然后让 agent 按 `SKILL.md` 为项目接入 FWID。`SPEC.md` 是规范主文档，`SKILL.md` 共用同一套规则。
