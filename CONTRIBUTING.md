# 贡献指南

感谢您对 PRAXIS 项目的关注！我们欢迎任何形式的贡献。

## 如何贡献

### 报告问题

1. 使用 GitHub Issues 报告 bug
2. 提供详细的问题描述、复现步骤和环境信息
3. 如果可能，提供错误日志或截图

### 提交代码

1. Fork 本仓库
2. 创建您的特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交您的更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 创建一个 Pull Request

### 开发环境设置

```bash
# 克隆仓库
git clone https://github.com/your-username/Praxis.git
cd Praxis

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或
venv\Scripts\activate  # Windows

# 安装依赖
pip install -e ".[all]"

# 运行测试
pytest tests/
```

### 代码规范

- 使用 Python 3.11+
- 遵循 PEP 8 代码规范
- 为新功能添加测试
- 更新相关文档

### 提交信息规范

使用清晰的提交信息：

```
feat: 添加新功能
fix: 修复 bug
docs: 更新文档
style: 代码格式调整
refactor: 代码重构
test: 添加测试
chore: 构建过程或辅助工具的变动
```

## 许可证

通过贡献代码，您同意您的贡献将在 MIT 许可证下发布。

## 联系方式

如有任何问题，请通过 GitHub Issues 联系我们。