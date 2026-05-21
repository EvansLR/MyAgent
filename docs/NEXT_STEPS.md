# MyAgent 褰撳墠鐘舵€佷笌涓嬩竴姝?
杩欎唤鏂囨。鐢ㄤ簬璺ㄥ璇濈画鎺ャ€傛柊瀵硅瘽寮€濮嬫椂鍏堣杩欓噷锛屽啀鎸夐渶璇荤浉鍏虫ā鍧楁枃妗ｅ拰浠ｇ爜銆?
## 褰撳墠椤圭洰瀹氫綅

MyAgent 褰撳墠瀹氫綅鏄細

```text
涓€涓?local-first銆佽交閲忋€佸彲鏁欏銆佸彲闈㈣瘯璁茶В鐨勪釜浜哄姪鐞?Agent runtime銆?```

褰撳墠闃舵涓嶈拷姹傜敓浜х骇骞冲彴澶嶆潅搴︼紝浼樺厛淇濊瘉锛?
- 涓婚摼璺ǔ瀹氬彲杩愯銆?- 鏍稿績妯″潡杈圭晫娓呮銆?- 鏂囨。鍜屽疄鐜颁竴鑷淬€?- 鍏抽敭鍙栬垗鑳借娓呮銆?- 鍚庣画鏂瑰悜鏈夎褰曪紝浣嗕笉杩囨棭鍋氶噸鍨嬬郴缁熴€?
## 褰撳墠涓婚摼璺兘鍔?
宸茬粡鍏峰骞跺湪浠ｇ爜涓彲瑙佺殑鑳藉姏锛?
- CLI Channel / MessageBus / AgentLoop
- ContextBuilder锛氶绠楁帶鍒躲€乭istory 瑁佸壀銆乧onversation summary銆乼race report
- OpenAI-compatible provider 鍜?EchoProvider
- ToolRegistry 涓庨粯璁ゅ伐鍏?- Filesystem tools锛歚list_dir`銆乣read_file`銆乣write_file`銆乣edit_file`銆乣copy_file`銆乣move_file`
- Shell tool锛歚execute_command`
- Memory tools 鍜?Markdown-backed memory
- Skills 鎵弿銆佹寜闇€鍔犺浇鍜?turn-scoped active skill trace
- MCP stdio / HTTP / SSE 宸ュ叿鎺ュ叆
- SubAgent 鍚屾濮旀墭
- JSONL trace銆乮nspect/report/viewer
- Feishu Gateway
- CronService
- MessageTool

甯哥敤鍏ュ彛锛?
```text
python -m myagent
python -m myagent gateway

python -m myagent trace latest
python -m myagent trace show --limit 20
python -m myagent trace context
python -m myagent trace report
python -m myagent trace viewer
```

## 鏈€杩戝畬鎴?
### Context

ContextBuilder 宸插畬鎴愬綋鍓嶉樁娈电殑涓昏涓婁笅鏂囨帶鍒讹細

- Context compaction now uses explicit limits: memory_token_limit, summary_token_limit, raw_history_token_limit, and raw_history_target_tokens.
- ContextBuilder assembles prepared context and reports estimates; it no longer drops system sections through ratio-based priority budgeting.
- Raw history compaction preserves useful information through MemoryExtractor, folds old history into Conversation Summary, then prunes the folded raw messages from process memory.
璁捐璁板綍锛?
- `docs/modules/CONTEXT_BUILDER.md`

### Memory

Memory 宸蹭粠鏃?JSONL recall 涓昏矾寰勮浆鍚?Markdown-backed workspace锛?
```text
MEMORY.md
  绋冲畾闀挎湡璁板繂锛岄粯璁ゅ彲杩涘叆涓婁笅鏂囥€?
MEMORY_PROPOSALS.md
  涓存椂闀挎湡璁板繂鍊欓€夊尯锛涘畾鏃?consolidation 鍚庡綊妗ｅ苟娓呯┖锛岄伩鍏嶉暱鏈熷爢绉€?
daily/YYYY-MM-DD.md
  杩戞湡宸ヤ綔瑙傚療銆佷复鏃朵笂涓嬫枃銆乷pen loop銆?```

褰撳墠 Memory 鍙栬垗锛?
- `memory_propose_long_term` 榛樿 `apply=false`锛屽厛鍐?proposal銆?- 鐢ㄦ埛鏄庣‘瑕佹眰鈥滆浣忊€濈殑绋冲畾璧勬枡鎵嶄娇鐢?`apply=true` 鍐欏叆 `MEMORY.md`銆?- `MemoryExtractor` 姣忚疆鍚庤繍琛岋紝浣嗗簲淇濆畧鍐欏叆锛屽彧鎶藉彇鏈潵浠嶄細褰卞搷鏈嶅姟鐢ㄦ埛鐨勪俊鎭€?- 涓嶆柊澧?`MemoryCurator`銆?- 涓嶅仛浜哄伐 review UI銆?- proposal 涓嶄綔涓洪暱鏈熷緟鍔炴睜銆?- 浣庣疆淇″害鍊欓€夊畞鍙湪 consolidation 鍚庡綊妗ｅ嚭涓婚摼璺紝涔熶笉瑕佹棤闄愮暀鍦ㄥ綋鍓?proposal 鏂囦欢閲屻€?
璁捐璁板綍锛?
- `docs/modules/MEMORY.md`
- `docs/modules/MEMORY_PHASE2_RESEARCH.md`

### Skills

Skills v2 宸插舰鎴愭渶灏忓彲瑙傚療闂幆锛?
- `skill_get(skill_id)` 鎸夐渶鍔犺浇瀹屾暣 `SKILL.md`銆?- 鎴愬姛鍔犺浇浼氳褰?`skill_loaded`銆?- turn-scoped active skills 浼氳褰?`active_skill_set`銆?- SubAgent 鍙户鎵跨揣鍑戠殑 parent active skill context銆?- 鏆備笉鍋氳嚜鍔?SkillSelector銆乸ersistent active skills 鎴?skill-defined tool permissions銆?
璁捐璁板綍锛?
- `docs/modules/SKILLS.md`

### SubAgent

SubAgent 宸茶繘鍏ュ彲鐢ㄩ樁娈碉細

- `delegate_task` 宸叉帴鍏ヤ富 Agent銆?- 鍐呯疆 profile锛歚researcher`銆乣reviewer`銆乣interviewer`銆?- 鏀寔 profile-specific child tool allowlist銆?- 鏀寔鑷姩濮旀墭绛栫暐锛屼絾浠嶄繚鎸佸悓姝ャ€佺煭鐢熷懡鍛ㄦ湡銆?
褰撳墠杈圭晫锛?
- 瀛?Agent 鍙互璇绘湰鍦版枃浠跺拰浣跨敤鍙 web 宸ュ叿銆?- 瀛?Agent 涓嶅啓鏂囦欢銆?- 瀛?Agent 涓嶉€掑綊濮旀墭銆?- 瀛?Agent 涓嶈幏寰椾换鎰?MCP 宸ュ叿鏉冮檺銆?
璁捐璁板綍锛?
- `docs/modules/SUBAGENT.md`

### Gateway / Cron / Message

Feishu Gateway銆丆ronService銆丮essageTool 宸茶惤鍦帮細

- Gateway 妯″紡杩愯 ChannelManager + AgentLoop + CronService銆?- Feishu 瀹℃壒璇锋眰浼氬洖鍒板綋鍓?chat锛屽苟浠?interactive card 灞曠ず鍏佽/鎷掔粷鎸夐挳銆?- Feishu 鏅€氬洖澶嶄細灏?Markdown-ish 鍐呭杞垚 `post` 瀵屾枃鏈紝鐭函鏂囨湰浠嶇敤 `text`銆?- Gateway 宸叉帴鍏ュ悓涓€鏉?approval callback锛涢渶瑕佸鎵圭殑宸ュ叿鎿嶄綔浼氳矾鐢卞洖褰撳墠 Feishu chat銆?- Shell tool 宸叉敮鎸佸父瑙?PowerShell 鍙绠￠亾锛屼緥濡?`Get-Process | Measure-Object | Select-Object ...` 涓嶅啀璇Е鍙戝鎵广€?- CronService 鏀寔 `every` / `at` / `once`銆?- 鐢ㄦ埛 cron 浼氳矾鐢卞洖鍒涘缓鏃剁殑 channel/chat_id銆?- 绯荤粺 cron 浼氭敞鍐?`memory_consolidation`銆?- MessageTool 鏀寔 Agent 鏄惧紡鍙戦€佹秷鎭拰鏂囦欢锛屽苟鎶戝埗閲嶅鏈€缁堝洖澶嶃€?
## 鏈€杩戦獙璇?
鏈€杩戝叏閲忔祴璇曪細

```text
python -m pytest
257 passed
```

鏈€杩?Feishu 闀胯繛鎺ョǔ瀹氭€т慨姝ｏ細

```text
python -m pytest tests/test_channels_feishu.py
23 passed

python -m pytest tests/test_channels_feishu.py tests/test_cli_channel.py tests/test_shell_tool.py tests/test_channels_manager.py
65 passed

python -m pytest
257 passed
```

鏈€杩戜唬鐮佹敹鏁涙竻鐞嗭細
- 鍒犻櫎鍙墿娴嬭瘯寮曠敤鐨勬棫渚挎嵎 API锛歚ContextBuilder.build_messages`銆乣AgentLoop.history_for`銆乣AgentLoop.conversation_summary_for`銆乣MessageBus.inbound_size/outbound_size`銆乣CronService.get_job`銆乣WorkspaceLoader.load_all`銆?- 鍒犻櫎鏃?JSONL memory 鏃朵唬閬楃暀鐨?`MemoryEntry` 缁撴瀯锛涘綋鍓嶄富绾夸娇鐢?Markdown-backed memory銆?- 瀵瑰簲娴嬭瘯鏀逛负楠岃瘉涓婚摼璺涓烘垨鐜版湁鏍稿績鎺ュ彛锛岄伩鍏嶆祴璇曠户缁€滀緵鍏烩€濅笉鍐嶄娇鐢ㄧ殑鏃т唬鐮併€?
瀹炵幇璁板綍锛?- Feishu WebSocket 澧炲姞澶栧眰閲嶈繛寰幆锛涘鏋?lark-oapi `client.start()` 寮傚父閫€鍑烘垨鎰忓杩斿洖锛実ateway 杩涚▼浼氱瓑寰?5 绉掑悗閲嶅缓 WSClient銆?- tenant_access_token 璁板綍杩囨湡鏃堕棿锛屽彂閫佸墠鎻愬墠鍒锋柊锛涘彂閫佸け璐ヨ嫢鍛戒腑 token 澶辨晥绫婚敊璇紝浼氬埛鏂板悗閲嶈瘯涓€娆°€?- 鍙戦€佸け璐ャ€乼oken 鍒锋柊澶辫触銆乄ebSocket 閫€鍑轰細鎵撳嵃鍙璇婃柇锛岄伩鍏?gateway 鐪嬭捣鏉ヨ繕娲荤潃浣嗙敤鎴蜂晶鏃犲搷搴斻€?- 瀹℃壒璇锋眰鍦?token 涓嶅彲鐢ㄦ椂浼氱洿鎺ヨ繑鍥炴嫆缁濈粨鏋滐紝閬垮厤 future 姘镐箙鎸傝捣銆?
鏈€杩戠湡瀹炴笭閬?smoke test锛?
```text
Feishu Gateway smoke test passed.
楠岃瘉椤癸細/new銆佸彧璇?shell 鏌ヨ銆佸瘜鏂囨湰鍥炲銆侀」鐩姸鎬佹€荤粨銆佸鎵瑰崱鐗囥€?```

鏈€杩?Memory focused verification锛?
```text
python -m pytest tests/test_memory_tools.py tests/test_memory_consolidator.py tests/test_agent_memory.py
14 passed
```

## 褰撳墠寤鸿

鐭湡涓嶈缁х画妯悜鍫嗗姛鑳姐€備笅涓€姝ュ缓璁粠椤圭洰鏉愭枡銆佷綋楠岃竟鐣屽拰鐪熷疄浣跨敤鍙嶉鍏ユ墜锛?
1. 淇濇寔褰撳墠涓婚摼璺ǔ瀹氾紝浼樺厛淇湡瀹炰娇鐢ㄤ腑鏆撮湶鐨勫崱鐐广€?2. 鍚庣画濡傜户缁紭鍖栧伐鍏蜂綋楠岋紝浼樺厛鍗曠嫭璁捐 `allow / confirm / deny` 椋庨櫓鍒嗗眰锛屽噺灏戜綆椋庨櫓鎿嶄綔鐨勫鎵规墦鏂€?3. Memory 鍐欏叆璐ㄩ噺鏆備笉鍋氫笓椤硅瀵燂紱瀹冧环鍊奸珮锛屼絾褰撳墠涓嶅鏄撳彲闈犺瘎浼帮紝閬垮厤涓轰簡瑙傚療鑰岃瀵熴€?4. 濡傞渶缁х画澧炲己锛屼紭鍏堣ˉ灏忔枃妗ｃ€佸皬娴嬭瘯鍜岀湡瀹為獙鏀舵竻鍗曪紝涓嶆柊澧為噸鍨嬫ā鍧椼€?
宸ュ叿鏉冮檺绛栫暐宸茬粡鏆撮湶鍑衡€滃鎵瑰亸澶氣€濈殑浣撻獙闂锛屼絾褰撳墠涓嶉樆濉炰富鍔熻兘銆傚悗缁彲浠ュ崟鐙璁?`allow / confirm / deny` 椋庨櫓鍒嗗眰锛屼笉寤鸿澶瑰湪 Gateway 鏀跺彛閲屽仛銆?
涓嶅缓璁綋鍓嶇珛鍒诲仛锛?
- 鏂板 `MemoryCurator`銆?- 浜哄伐 memory review UI銆?- 鍚戦噺搴?/ SQLite / knowledge graph memory銆?- 鑷姩 SkillSelector銆?- persistent active skills銆?- 瀛?Agent 鍐欐枃浠躲€?- recursive subagent delegation銆?- 閲嶅瀷 workflow graph runtime銆?- QQ Channel 瀹為檯鎺ュ叆銆?
## 鎵嬪姩妫€鏌ヨ矾寰?
### CLI 鍩烘湰閾捐矾

```text
python -m myagent
```

寤鸿瑙傚療锛?
- 鏅€氶棶绛旀槸鍚︽甯搞€?- 鏄惁鏈夋剰澶?memory 鍐欏叆銆?- conversation summary 鏄惁鍦ㄩ暱瀵硅瘽鍚庢洿鏂般€?
### Feishu Gateway smoke test

```text
python -m myagent gateway
```

褰撳墠鐘舵€侊細宸茬敱鐢ㄦ埛鐪熷疄楠岃瘉閫氳繃銆?
寤鸿鍦?Feishu 浼氳瘽閲屼緷娆℃祴璇曪細

```text
/new
甯垜鏌ョ湅褰撳墠杩涚▼鏁伴噺
鐢ㄦ爣棰樺拰鍒楄〃鎬荤粨涓€涓嬭繖涓」鐩幇鍦ㄨ兘鍋氫粈涔?甯垜鎬荤粨涓€涓?docs/NEXT_STEPS.md 鐨勫綋鍓嶇姸鎬?甯垜鍏抽棴鎵嬫満杩炴帴搴旂敤
```

棰勬湡瑙傚療锛?
- `/new` 浼氬紑濮嬩竴涓柊鐨?Feishu 浼氳瘽涓婁笅鏂囥€?- 杩涚▼鏁伴噺鏌ヨ搴旇蛋鍙 shell 绠￠亾锛屼笉瑙﹀彂瀹℃壒銆?- 甯︽爣棰樺拰鍒楄〃鐨勫洖澶嶅簲娓叉煋涓?Feishu `post` 瀵屾枃鏈紝鑰屼笉鏄甫琛屽彿鐨勭函 Markdown銆?- 鎬荤粨椤圭洰鐘舵€佹椂搴旇兘璋冪敤鏂囦欢/涓婁笅鏂囧伐鍏峰苟缁欏嚭鏈€缁堝洖澶嶃€?- 鍏抽棴鎵嬫満杩炴帴搴旂敤杩欑被鏉€杩涚▼鎿嶄綔搴旇Е鍙?Feishu interactive card 瀹℃壒锛涚敤鎴风偣鍏佽鍚庡啀鎵ц锛岀偣鎷掔粷鍒欒繑鍥炴嫆缁濈粨鏋溿€?- 濡傛灉 Windows 鏉冮檺涓嶈冻锛屽鎵归€氳繃鍚庝粛鍙兘杩斿洖 `Access is denied`锛岃繖鏄郴缁熸潈闄愰檺鍒讹紝涓嶆槸鍗＄墖娓叉煋澶辫触銆?
### Trace

```text
python -m myagent trace latest
python -m myagent trace show --limit 10
python -m myagent trace context
python -m myagent trace report
python -m myagent trace viewer
```

寤鸿瑙傚療锛?
- `context_built`
- `context_dropped`
- `conversation_summary_updated`
- `memory_candidates_saved`
- `skill_loaded`
- `active_skill_set`
- `subagent_start`

### SubAgent + Skills

缁欎竴涓渶瑕佸厛鍔犺浇 skill銆佸啀閫傚悎濮旀墭鏂囦欢鎺㈢储鐨勭湡瀹炰换鍔★紝瑙傚療锛?
- 鏄惁鍑虹幇 `active_skill_set`
- 鏄惁鍑虹幇 `subagent_start`
- `subagent_start` 鏄惁甯?`inherited_active_skills`

## 鐢ㄦ埛鍋忓ソ涓庡伐浣滅害鏉?
寮€鍙戞椂缁х画閬靛畧锛?
- 閲嶈瀹炵幇鍓嶅厛鏇存柊鐩稿叧鏂囨。銆?- 姣忎釜鏍稿績妯″潡淇濇寔鐙珛妯″潡鏂囨。銆?- 鏀瑰畬鍚庡洖濉疄鐜拌鏄庡拰楠岃瘉鏂瑰紡銆?- 鍏堣鐢ㄦ埛纭锛屽啀鍋?Git 鎻愪氦銆?- 鎻愪氦鎸夋ā鍧楄竟鐣岃繘琛岋紝涓嶄负姣忎釜灏忔敼鍔ㄥ崟鐙彁浜ゃ€?- 涓嶆彁浜ょ湡瀹為厤缃€佸瘑閽ャ€乵emory銆乼race銆乧ache銆佹湰鍦版祴璇曠洰褰曘€?- 椤圭洰浼樺厛鏈嶅姟瀛︿範銆佹紨绀恒€侀潰璇曡〃杈撅紝閬垮厤杩囧害宸ョ▼鍖栥€?- 涓嶈涓€鍛宠繋鍚堢敤鎴凤紱鍙戠幇璁捐鍐茬獊鎴栧鏉傚害杩囬珮鏃惰鐩存帴鎸囧嚭銆?
## 缁帴椤哄簭

鏂板璇濈户缁繖涓」鐩椂锛屽缓璁寜涓嬮潰椤哄簭鎭㈠涓婁笅鏂囷細

1. 璇绘湰鏂囦欢銆?2. 璇?`docs/README.md` 浜嗚В鏂囨。鍦板浘銆?3. 蹇呰鏃惰 `docs/PHASE2_REVIEW_PLAN.md` 浜嗚В鍘嗗彶澶嶇洏鏂规硶銆?4. 鎸変换鍔¤妯″潡鏂囨。锛?   - `docs/modules/CONTEXT_BUILDER.md`
   - `docs/modules/MEMORY.md`
   - `docs/modules/SKILLS.md`
   - `docs/modules/SUBAGENT.md`
   - `docs/modules/TRACE.md`
5. 鍐嶇湅浠ｇ爜鍜屾祴璇曘€?
## 鏈€杩戞彁浜?
```text
94b7849 feat: improve feishu tool interactions
ec90d32 feat: add feishu approval cards
3fa3664 fix: shell tool hangs in gateway mode + encoding issues
70f79e8 feat: add execute_command tool for shell command execution
dbe2f47 feat: add /new command for all channels to start fresh session
22ab495 docs: consolidate project status docs
b884876 docs: clarify temporary memory proposals
b992e5f feat: clarify memory proposal workflow
```

## 2026-05-20 Observability Removal and Runtime Assembly Refactor

Recently completed:

- Removed runtime trace/report plumbing from the agent path.
- Removed the `myagent.tracing` package, trace CLI commands, and trace-focused tests.
- Simplified `ContextBuilder` back to assembling messages and sections; context report data classes and `build_messages_with_report` are gone.
- Replaced trace-oriented skill callbacks with a small active-skill callback used only for current-turn context.
- Added `AgentMemoryServices` so memory store, extractor, consolidator, compressor, and memory tool registration are owned by the memory layer.
- Added `AgentContextRuntime` so ContextBuilder, conversation summary, session history, profile, skills, and active skill state are assembled inside the context layer instead of inside `AgentLoop`.
- Moved shared compression helpers to `myagent.text.compression` so Memory no longer depends on Context for generic text utilities.
- Changed memory proposal consolidation and visible memory compression to use a small `save_memory` tool-call contract and canonical MEMORY.md validation before writing.
- `AgentLoop` now stays closer to orchestration: bus, provider, module runtimes, tool loop, cron bridge, and turn processor wiring.

Verification:

```text
python -m compileall -q myagent
python -m pytest
242 passed
```

Next recommended step:

- Review whether `AgentLoop` should also delegate remaining default non-memory tool registration (`delegate_task`, `cron`) to a small tool-runtime assembly helper.
- If the current diff looks good, commit it as one focused refactor.

## 2026-05-21 MessageTool Removal

Recently completed:

- Removed the default model-facing `MessageTool`.
- Removed duplicate reply suppression from `AgentTurnProcessor`; one turn now has one normal final reply path.
- Kept channel-level media support intact through `OutboundMessage.media` and channel implementations.
- Added `attach_file` as a small final-reply attachment tool. It records existing files on the turn state and does not send a separate message.

Current routing model:

- Cron and Gateway inputs carry `channel` and `chat_id` in `InboundMessage`.
- Agent runtime publishes the final response as `OutboundMessage(channel, chat_id, content, media)`.
- Feishu-specific formatting and media sending stay inside the Feishu channel layer.

Verification:

```text
python -m compileall -q myagent
python -m pytest tests/test_agent_loop.py tests/test_channels_feishu.py tests/test_cli_channel.py tests/test_tool_registry.py
59 passed

python -m pytest
248 passed
```

## 2026-05-21 Shell Risk Classification

Recently completed:

- Extracted shell approval decisions into `myagent.tools.shell_risk`.
- Added `ShellRisk.ALLOW / CONFIRM / DENY` as the small policy model.
- Allowed common read-only queries, PowerShell read-only pipelines, version probes, read-only Git commands, and `python -m pytest` / `python -m compileall` without approval.
- Kept mutating commands, redirection, command chaining, unknown commands, and inline Python code behind approval.

Verification:

```text
python -m compileall -q myagent
python -m pytest tests/test_shell_tool.py tests/test_agent_loop.py tests/test_tool_registry.py
49 passed

python -m pytest
259 passed
```

## 2026-05-21 Explicit Tool Execution Context

Recently completed:

- Removed the turn-local approval `ContextVar`.
- Added `ToolExecutionContext` for per-turn tool runtime services.
- Approval routing is now explicit: tool loop builds a context with session, turn, channel, chat, attachments, and approval callback.
- Shell and filesystem tools request approval through the explicit context when running inside AgentLoop.
- Direct tool tests still support prompt-only approval callbacks for simple unit coverage.
- `delegate_task` no longer inherits parent active-skill context automatically. If a subagent needs skill-specific guidance, the main agent should include it explicitly in `task` or `context`.

Verification:

```text
python -m compileall -q myagent
python -m pytest tests/test_cli_channel.py tests/test_shell_tool.py tests/test_filesystem_tools.py tests/test_agent_loop.py tests/test_cron_tool.py tests/test_tool_registry.py
105 passed

python -m pytest
258 passed
```

## Profile / Memory / Runtime 杈圭晫鏀舵暃

褰撳墠鎸夋垚鐔?coding-agent 宸ュ叿鐨勫仛娉曪紝鎶娾€滀汉鍐欑殑绋冲畾鎸囦护鈥濆拰鈥淎gent 鑷繁璁颁綇鐨勫唴瀹光€濆垎寮€锛?
```text
~/.myagent/profile/
  AGENT.md   # MyAgent 杩愯鏃惰韩浠姐€佸師鍒欍€佽涓洪鏍?  USER.md    # 鐢ㄦ埛璧勬枡鍜岀ǔ瀹氬亸濂?  TOOLS.md   # 宸ュ叿浣跨敤鎻愮ず

~/.myagent/memory/
  MEMORY.md
  MEMORY_PROPOSALS.md
  daily/YYYY-MM-DD.md

~/.myagent/runtime/
  cron/jobs.json
```

璇箟杈圭晫锛?- `AGENTS.md` 鏄紑鍙戣繖涓?repo 鐨勫崗浣滆鍒欙紝涓嶈繘鍏?MyAgent runtime prompt銆?- `profile/AGENT.md` 鏄?MyAgent 杩愯鏃?profile锛岀被浼?Claude Code 鐨?`CLAUDE.md` / Cursor rules銆?- `memory/MEMORY.md` 鏄暱鏈熻蹇嗭紝鍙瓨鐢ㄦ埛鍋忓ソ銆侀暱鏈熶簨瀹炪€佺ǔ瀹氱洰鏍囥€?- session history銆乧onversation summary銆乤ctive skills 鏄繘绋嬪唴 session state锛屼笉鏄?long-term memory銆?- trace銆乧ron jobs 鏄?runtime data锛屼笉鏄?memory銆?
閲嶅懡鍚嶇瓥鐣ワ細
- 涓嶄繚鐣?`~/.myagent/workspace/` runtime 鍏煎璇诲彇锛岄伩鍏?workspace 姒傚康缁х画姹℃煋 profile / memory / runtime銆?- 鏃?profile 鏂囦欢闇€瑕佹墜鍔ㄧЩ鍔ㄥ埌 `~/.myagent/profile/`銆?- 鏃?memory 鏂囦欢闇€瑕佹墜鍔ㄧЩ鍔ㄥ埌 `~/.myagent/memory/`銆?- 鏃?cron 鏂囦欢闇€瑕佹墜鍔ㄧЩ鍔ㄥ埌 `~/.myagent/runtime/cron/jobs.json`銆?- 浠ｇ爜灞傚垹闄?`myagent.workspace.WorkspaceLoader`锛屾敼涓?`myagent.profile.ProfileLoader`銆?
## 2026-05-20 Refactor Status

Recently completed:

- Committed the prior session-history extraction as `157ca5e refactor: extract agent session history`.
- Added `docs/REFACTOR_ROADMAP_2026-05-20.md`.
- Applied the roadmap as a behavior-preserving complexity/redundancy cleanup.

Current refactor shape:

- `myagent/agent/messages.py` owns shared tool-call chat message helpers.
- `myagent/agent/skill_state.py` owns turn-scoped active skill state.
- `myagent/agent/cron_bridge.py` owns cron-to-agent message routing and memory consolidation job handling.
- `myagent/cli/runtime.py` owns shared CLI/gateway runtime assembly.
- `myagent/tools/filesystem.py` now shares copy/move validation logic.

Verification run in this session:

```text
python -m pytest tests/test_agent_loop.py tests/test_subagent.py tests/test_agent_trace.py
python -m pytest tests/test_agent_skills.py tests/test_subagent.py tests/test_context_builder.py
python -m pytest tests/test_cron_service.py tests/test_cron_tool.py tests/test_agent_memory.py
python -m pytest tests/test_filesystem_tools.py
python -m pytest tests/test_cli_channel.py tests/test_channels_manager.py tests/test_channels_feishu.py
python -m pytest

266 passed
```

Next recommended step:

- Review the cron scheduled-task prompt wording change caused by moving the old mojibake text into a new module.
- If tests pass and the diff looks good, commit this cleanup as one focused refactor commit.

## 2026-05-20 Context Compaction Design

Current design work:

- Added `docs/modules/CONTEXT_COMPACTION_DESIGN.md`.
- The design separates fixed system prompt, visible memory, conversation summary, and raw history.
- System prompt is not compressed automatically.
- Memory and summary each get a simple token limit and LLM compression loop.
- Raw history gets its own compaction threshold; before old history is folded into summary, `MemoryExtractor` preserves future-useful information into archive/proposals.

Next recommended step:

- Review the design before implementation.
- If accepted, start with tests for memory compression, summary compression, and raw history compaction thresholds.

## 2026-05-20 Context Compaction Implementation

Recently completed:

- Implemented explicit token-limit based compaction for visible memory, summary, and raw history.
- `ContextBuilder` now assembles prepared context instead of dropping sections through a shared priority budget.
- Added a shared compression loop used by summary and visible memory compaction.
- Added visible-memory compression before context build when `MEMORY.md` exceeds `memory_token_limit`.
- Added summary compression when conversation summary exceeds `summary_token_limit`.
- Replaced ratio-based raw history compaction with `raw_history_token_limit` and `raw_history_target_tokens`.
- Pruned summarized raw history from process memory after successful compaction, so long-running processes do not retain invisible old turns forever.

Verification:

```text
python -m pytest
268 passed
```

Next recommended step:

- Review the context compaction diff and then commit if acceptable.
