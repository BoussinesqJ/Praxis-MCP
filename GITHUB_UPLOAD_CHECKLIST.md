# PRAXIS R1.0.0 GitHub 上传检查清单

> **上传前请逐项检查，确保安全**

---

## 一、安全检查 ✅

- [ ] 确认无硬编码 API Key
- [ ] 确认无真实个人信息（姓名、身份证、银行卡）
- [ ] 确认 investors/user/ 已加入 .gitignore
- [ ] 确认 data/ledger/transactions.jsonl 已加入 .gitignore
- [ ] 确认 data/decisions/decision_records.jsonl 已加入 .gitignore
- [ ] 确认 .env 文件已加入 .gitignore

---

## 二、代码检查 ✅

- [ ] 运行测试：`python -m pytest tests/ -v`
- [ ] 确认 418 个测试全部通过
- [ ] 确认无语法错误
- [ ] 确认无 import 错误

---

## 三、文档检查 ✅

- [ ] README.md 已更新（MCP 工具数、测试数）
- [ ] docs/ROADMAP.md 已更新
- [ ] docs/DEVELOPMENT_SUMMARY.md 已更新
- [ ] CHANGELOG.md 已创建

---

## 四、Git 检查 ✅

- [ ] .gitignore 已配置
- [ ] 无敏感文件在 git 跟踪中
- [ ] 提交信息清晰明确
- [ ] 版本标签已准备（r1.0.0）

---

## 五、上传步骤

### 5.1 创建 GitHub 仓库

1. 登录 GitHub
2. 点击 "New repository"
3. 填写信息：
   - **Repository name**: `praxis`
   - **Description**: `PRAXIS - 投研纪律系统 R1.0`
   - **Visibility**: ✅ **Public**（公开仓库）
   - **Initialize this repository**: ❌ 不勾选（已有代码）
4. 点击 "Create repository"

### 5.2 上传代码

```bash
cd "praxis-r1.0"

# 添加远程仓库
git remote add origin git@github.com:<your-username>/praxis.git

# 推送代码
git push -u origin main

# 创建版本标签
git tag -a r1.0.0 -m "PRAXIS R1.0.0 - 开源版本"
git push origin r1.0.0
```

### 5.3 验证上传

1. 访问 GitHub 仓库页面
2. 确认文件结构正确
3. 确认 README.md 显示正常
4. 确认无敏感文件泄露

---

## 六、上传后操作

### 6.1 设置仓库

1. **Settings** → **General**
   - 确认 Visibility 为 Public
   - 确认 Description 已填写

2. **Settings** → **Branches**
   - 添加分支保护规则（可选）
   - 要求 Pull Request 审查

3. **Settings** → **Secrets and variables**
   - 添加 GitHub Actions 密钥（如需要）

### 6.2 创建 Release

1. 点击 "Releases"
2. 点击 "Create a new release"
3. 选择标签：r1.0.0
4. 填写发布说明：
   - 标题：PRAXIS R1.0.0 - 开源版本
   - 描述：复制 CHANGELOG.md 内容
5. 点击 "Publish release"

---

## 七、紧急情况处理

### 如果发现敏感信息泄露

1. **立即删除仓库**
   ```bash
   # 在 GitHub Settings → Danger Zone → Delete this repository
   ```

2. **清理 Git 历史**
   ```bash
   # 使用 git filter-branch 或 BFG Repo-Cleaner
   # 清除敏感文件的所有历史记录
   ```

3. **重新创建仓库并上传**

---

## 八、联系方式

如有问题，请通过 GitHub Issues 联系我们。

---

**检查清单完成，准备上传！** ✅
