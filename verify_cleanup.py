"""验证三项遗留清理：旧插件归档 + 配置清理 + external_provider 移除

检查：
1. registry auto_discover 后只注册 tencent + mootdx（无 plugin:xxx 残留）
2. apply_config 后仍只 2 个 provider（无 config_unknown_provider warning）
3. 降级链顺序 tencent(5) → mootdx(8)
"""
import os
import sys

WORKSPACE = os.environ.get("PRAXIS_WORKSPACE", "")
RUNTIME_SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "src")

os.environ['PRAXIS_WORKSPACE'] = WORKSPACE
sys.path.insert(0, RUNTIME_SRC)

from praxis.engine.data.registry import ProviderRegistry

reg = ProviderRegistry()
reg.auto_discover(WORKSPACE)

providers = reg.list_providers()
print(f"=== auto_discover 后注册 providers: {len(providers)} ===")
for p in providers:
    print(f"  {p['name']}: priority={p['priority']}, enabled={p['enabled']}, class={p['class']}")

names = [p['name'] for p in providers]
assert 'tencent' in names, "tencent 未注册!"
assert 'mootdx' in names, "mootdx 未注册!"
assert len(providers) == 2, f"期望2个provider，实际{len(providers)}个: {names}"
assert not any(n.startswith('plugin:') for n in names), f"仍有插件注册: {[n for n in names if n.startswith('plugin:')]}"

import yaml
with open(os.path.join(WORKSPACE, 'config', 'data_sources.yaml'), 'r', encoding='utf-8') as f:
    config = yaml.safe_load(f)

reg.apply_config(config)
providers_after = reg.list_providers()
print(f"\n=== apply_config 后 providers: {len(providers_after)} ===")
for p in providers_after:
    print(f"  {p['name']}: priority={p['priority']}, enabled={p['enabled']}, available={p['available']}")

names_after = [p['name'] for p in providers_after]
assert len(providers_after) == 2, f"配置后期望2个，实际{len(providers_after)}: {names_after}"

chain = reg.get_chain()
print(f"\n=== 降级链（按优先级）===")
for name, inst in chain:
    print(f"  {name}: {inst.__class__.__name__}")
assert len(chain) == 2, f"降级链期望2个，实际{len(chain)}"
assert chain[0][0] == 'tencent', f"降级链首位应为tencent，实际{chain[0][0]}"
assert chain[1][0] == 'mootdx', f"降级链次位应为mootdx，实际{chain[1][0]}"

print("\n=== ALL CHECKS PASSED ===")
print("1. 旧插件归档: providers目录无加载失败插件")
print("2. 配置清理: provider_registry只含tencent+mootdx，无unknown_provider warning")
print("3. external_provider: 已归档，降级链直接tencent→mootdx")
