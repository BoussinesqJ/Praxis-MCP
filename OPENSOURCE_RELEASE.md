# PRAXIS R1.0 开源版本说明

## 版本信息

- **版本号**: r1.0.0
- **基于**: v1.4.0
- **发布日期**: 2026-06-08
- **许可证**: MIT

## 主要变更

### 1. 版本号更新
- `pyproject.toml`: 1.4.0 → r1.0.0
- `praxis/__init__.py`: 1.4.0 → r1.0.0
- `praxis/cli.py`: 1.4.0 → r1.0.0
- `README.md`: v1.4.0 → r1.0.0
- `docs/ROADMAP.md`: v1.4.0 → r1.0.0

### 2. 开源文件添加
- `LICENSE`: MIT 开源协议
- `CONTRIBUTING.md`: 贡献指南
- `CHANGELOG.md`: 更新日志

### 3. 个人信息清理
- 移除硬编码的用户路径 (`C:\Users\77271\Desktop\Portfolio vault`)
- 替换个人信息:
  - `sanchisheng` → `example`
  - `grid_value_v9` → `demo`
  - `三尺生` → `示例投资者`
  - `BoussinesqJ` → `your-username`

### 4. 敏感信息检查
- ✅ 无硬编码 API 密钥
- ✅ 无硬编码密码
- ✅ 无硬编码私有域名
- ✅ 无个人文件路径

## 目录结构

```
praxis-r1.0/
├── praxis/                  # 源代码
│   ├── __init__.py
│   ├── cli.py
│   ├── mcp_server.py
│   ├── core/               # 核心模块
│   ├── engine/             # 引擎层
│   └── tools/              # MCP 工具
├── tests/                  # 测试套件
├── config/                 # 配置模板
├── docs/                   # 文档
├── providers/              # 数据源插件
├── scripts/                # 脚本工具
├── README.md
├── LICENSE
├── CONTRIBUTING.md
├── CHANGELOG.md
├── pyproject.toml
└── .gitignore
```

## 使用说明

### 安装

```bash
git clone https://github.com/your-username/Praxis.git
cd Praxis
pip install -e .
```

### 配置

```bash
# 设置环境变量
export PRAXIS_WORKSPACE="你的实际路径/Portfolio vault"

# 复制配置模板
cp config/trae_config.example.json config/trae_config.json
```

### 运行测试

```bash
python -m pytest tests/ -v
```

## 注意事项

1. **投资者数据**: 需要自行创建投资者配置文件
2. **策略文件**: 需要自行创建策略模板
3. **数据源**: 需要配置数据源插件（AKShare/Baostock 等）

## 开源准备清单

- [x] 版本号更新
- [x] 添加开源协议
- [x] 添加贡献指南
- [x] 添加更新日志
- [x] 清理个人信息
- [x] 清理敏感信息
- [x] 更新文档
- [x] 创建 GitHub 仓库
- [ ] 推送代码到 GitHub
- [ ] 创建 GitHub Release