#!/usr/bin/env python3
import re

# Load badges
badges = {}
with open('/challenge/input/roadmap-badges.conf') as f:
    content = f.read()
# Actually roadmap-badges.conf is included directly; parsing lines like "\"a\" \"7f\";"
# But default value handling? Let's parse directly.
badge_map = {}
for m in re.finditer(r'"([^"]+)"\s+"([^"]+)"', content):
    k,v = m.groups()
    badge_map[k]=v
# default is zz per roadmap-badges.conf first line: default "zz";
# We'll use default zz.

# Load default.conf
with open('/challenge/input/default.conf') as f:
    conf = f.read()

# Parse wp mappings: map $route $wp_XXXX { default ""; "~^.{N}(?<c>.)" $c; }
wp_to_pos = {}
for m in re.finditer(r'map \$route \$wp_([0-9a-f]+)\s*\{\s*default "";\s*"~\^\.\{(\d+)\}\(\?<c>\.\)" \$c;\s*\}', conf):
    wp, pos = m.groups()
    wp_to_pos[wp]=int(pos)

# Parse badge mappings: map $wp_XXXX $badge_YYYY { include roadmap-badges.conf; }
badge_to_wp = {}
for m in re.finditer(r'map \$wp_([0-9a-f]+) \$badge_([0-9a-f]+)\s*\{\s*include roadmap-badges\.conf;\s*\}', conf):
    wp, badge = m.groups()
    badge_to_wp[badge]=wp

# Parse cp mappings
# There are two forms: map $badge_XXXX $cp_YYYY { ... }  and map "${cp_XXXX}:${badge_YYYY}" $cp_ZZZZ { ... }
# We'll extract all
import re

cp_transitions = []  # list of (src_cp, badge, dst_cp, required_cp_val, required_badge_val, dst_val)
# single badge case
for m in re.finditer(r'map \$badge_([0-9a-f]+) \$cp_([0-9a-f]+)\s*\{\s*default "DETOUR";\s*"([^"]+)"\s+"([^"]+)";\s*\}', conf):
    badge, dst_cp, req_badge, dst_val = m.groups()
    cp_transitions.append((None, badge, dst_cp, None, req_badge, dst_val))

# double
for m in re.finditer(r'map "\$\{cp_([0-9a-f]+)\}:\$\{badge_([0-9a-f]+)\}" \$cp_([0-9a-f]+)\s*\{\s*default "DETOUR";\s*"([^:]+):([^"]+)"\s+"([^"]+)";\s*\}', conf):
    src_cp, badge, dst_cp, req_cp, req_badge, dst_val = m.groups()
    cp_transitions.append((src_cp, badge, dst_cp, req_cp, req_badge, dst_val))

# Build helpers
pos_to_wp = {v:k for k,v in wp_to_pos.items()}
badge_to_pos = {}
for badge, wp in badge_to_wp.items():
    pos = wp_to_pos[wp]
    badge_to_pos[badge]=pos

# reverse badge map char -> hex
char_to_hex = badge_map
hex_to_char = {v:k for k,v in badge_map.items() if k!="default"}

# Expected route from manual solving
flag = "[FLAG REDACTED]"
print(f"flag: {flag} len={len(flag)}")
assert len(flag)==41

# Compute route_len_ok
route_len_ok = 1 if len(flag)==41 else 0
print(f"route_len_ok={route_len_ok}")

# Compute wp values
wp_vals = {}
for wp, pos in wp_to_pos.items():
    wp_vals[wp]= flag[pos] if pos < len(flag) else ""

# Compute badge values
badge_vals = {}
for badge, wp in badge_to_wp.items():
    c = wp_vals[wp]
    badge_vals[badge]= badge_map.get(c, "zz")  # default zz
    # print(badge, wp, pos, c, badge_vals[badge])

# Show each position's char and badge
for pos in range(41):
    wp = pos_to_wp[pos]
    # find badge for this wp
    badge = None
    for b,w in badge_to_wp.items():
        if w==wp:
            badge=b
            break
    char = flag[pos]
    hexv = badge_vals[badge]
    print(f"pos {pos:02d} [FLAG REDACTED] [FLAG REDACTED] char '{char}' -> {hexv}")

# Simulate cp chain
# Need to order transitions as dependency; we have list but need iterative simulation
# Build dict dst_cp -> (src_cp, badge, req_cp, req_badge, dst_val)
trans_map = {}
for src_cp, badge, dst_cp, req_cp, req_badge, dst_val in cp_transitions:
    trans_map[dst_cp]=(src_cp, badge, req_cp, req_badge, dst_val)

# Simulate sequentially in topological order - start from initial cp_8a32 which has no src_cp
cp_vals = {}
# Evaluate in loop until stable
# Initialize all to DETOUR then iterate
# Actually map semantics: cp value is determined by evaluating condition: if src_cp == req_cp and badge == req_badge then dst_val else DETOUR
# For single badge case: if badge == req_badge then dst_val else DETOUR

# We need to evaluate in dependency order. We'll sort by requiring src_cp to be already computed.
# Let's attempt iterative until no change.
all_cps = set(trans_map.keys()) | set([src for src,_,_,_,_,_ in cp_transitions if src])

# Initialize
for cp in all_cps:
    cp_vals[cp]="DETOUR"
# But need to iterate
changed=True
iterations=0
while changed and iterations<100:
    changed=False
    iterations+=1
    for dst_cp, (src_cp, badge, req_cp, req_badge, dst_val) in trans_map.items():
        # get badge value
        bval = badge_vals.get(badge)
        if src_cp is None:
            # single
            new_val = dst_val if bval==req_badge else "DETOUR"
        else:
            src_val = cp_vals.get(src_cp, "DETOUR")
            new_val = dst_val if (src_val==req_cp and bval==req_badge) else "DETOUR"
        if cp_vals.get(dst_cp)!=new_val:
            cp_vals[dst_cp]=new_val
            changed=True

# Print cp chain in order of discovery following transitions sorted by dependency
# Let's reconstruct path to CLEARED
# Starting from cp_8a32 chain forwards
order = []
# Find path that leads to CLEARED
# We know final is cp_199f should be CLEARED
print("\nCP values:")
for cp,val in sorted(cp_vals.items()):
    print(f"[FLAG REDACTED] = {val}")

# Verify final
cp_199f = cp_vals.get("199f")
cp_199f_expected = "CLEARED"
print(f"\ncp_199f={cp_199f} expected CLEARED")

reached_cleared = 1 if cp_199f=="CLEARED" else 0
print(f"reached_cleared={reached_cleared}")
access = 1 if (reached_cleared==1 and route_len_ok==1) else 0
print(f"access={access}")

if access==1:
    print("SUCCESS: Access cleared, stakeholder.")
    print(f"FLAG: {flag}")
else:
    print("FAIL: Detour")

# Also verify each transition's required values correspond to derived hex
print("\nVerifying each transition requirement vs actual:")
for dst_cp, (src_cp, badge, req_cp, req_badge, dst_val) in trans_map.items():
    actual_badge = badge_vals.get(badge)
    actual_src = cp_vals.get(src_cp) if src_cp else None
    ok_badge = (actual_badge==req_badge)
    ok_src = (actual_src==req_cp) if src_cp else True
    pos = badge_to_pos.get(badge, "?")
    char = flag[pos] if isinstance(pos,int) else "?"
    print(f"dst [FLAG REDACTED]: need [FLAG REDACTED] (pos {pos} char '{char}') == {req_badge} actual {actual_badge} {'OK' if ok_badge else 'FAIL'}; need [FLAG REDACTED]=={req_cp} actual {actual_src} {'OK' if ok_src else 'FAIL'} -> {dst_val} vs actual {cp_vals[dst_cp]}")

# Alternative confirm by reverse solving: show mapping of required badge hex to char
print("\nReverse badge hex to char for each step:")
for src_cp, badge, dst_cp, req_cp, req_badge, dst_val in cp_transitions:
    if badge in badge_to_pos:
        pos = badge_to_pos[badge]
        # expected char is hex_to_char[req_badge]
        exp_char = hex_to_char.get(req_badge, "?")
        print(f"[FLAG REDACTED] requires [FLAG REDACTED] [FLAG REDACTED] = {req_badge} => char '{exp_char}' (actual flag pos {pos} = '{flag[pos]}') {'MATCH' if exp_char==flag[pos] else 'MISMATCH'}")
    else:
        print(f"badge {badge} not found")

