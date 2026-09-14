# Cache maintenance standard

LabOntology Creator 维护的是按 Skill 体系长期存在的紧凑图谱缓存，而不是一次性导入目录。每个 `suite_id` 对应一个稳定目录：

```text
labontology_<suite>_skill_cache/
├── cache-manifest.json
├── ontology.jsonl
├── source-index.json
└── runs/
```

## 维护原则

1. 同一 `suite_id` 始终更新同一个缓存目录；不同 suite 分开维护。
2. 导入的 Skill、合同、能力、流程和证据摘要写入 `ontology.jsonl`；可执行 Skill 保留在注册的源目录，图谱记录其运行位置和运行绑定。
3. 外部知识、设备和流程文件不复制到缓存；`source-index.json` 记录路径、哈希、类型、Skill 关联和更新时间。
4. 更新时保留原始来源、备注、更新时间和未决项；同一路径再次更新时替换旧索引记录，不产生重复记录。
5. 根目录 `cache-manifest.json` 保存图谱格式、suite 和更新时间，不保存临时目录内容。
6. 数据维护不会启用 Skill，也不会产生运行时执行记录；`runs/` 只保存运行产物。

## 用户知识更新

将用户在对话中提供的内容先整理为 Markdown、YAML 或 JSON，并保留原始语义。源文件应放在缓存之外，然后使用：

```powershell
python scripts/update_cache.py `
  --cache-dir C:\path\to\labontology_fdu_skill_cache `
  --source C:\path\to\new-knowledge.yaml `
  --kind device `
  --note "用户补充设备限制"
```

知识类型的选择标准：

| 类型 | 保存位置 | 适用内容 |
|---|---|---|
| `knowledge` | `source-index.json` + 图谱 Skill 注释 | 材料别名、数据格式、结果解释、通用规则 |
| `device` | `source-index.json` + 图谱证据 | 设备能力、动作、参数范围、资源和安全限制 |
| `workflow` | `source-index.json` + 图谱参考关系 | 节点顺序、分支条件、预期结果和任务约束 |

标准示例见 [examples/README.md](examples/README.md)。
