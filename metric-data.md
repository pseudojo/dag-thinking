/context


컨텍스트 창
39.3k / 200.0k (20%)
Messages
17.5k
8.8%
System tools
10.6k
5.3%
System prompt
6.7k
3.4%
Skills
3.3k
1.7%
MCP tools
1.8k
0.9%
MCP tools (deferred)
21.0k
10.5%
System tools (deferred)
12.1k
6.0%
Autocompact buffer
33.0k
16.5%
Free space
127.2k
63.6%

MCP 도구
22.7k
77
ccd_directory · mcp__ccd_directory__request_directory
173
ccd_session · mcp__ccd_session__dismiss_task
291
ccd_session · mcp__ccd_session__mark_chapter
329
ccd_session · mcp__ccd_session__spawn_task
776
ccd_session_mgmt · mcp__ccd_session_mgmt__archive_session
301
ccd_session_mgmt · mcp__ccd_session_mgmt__list_sessions
213
ccd_session_mgmt · mcp__ccd_session_mgmt__search_session_transcripts
209
ccd_session_mgmt · mcp__ccd_session_mgmt__send_message
259
Claude_in_Chrome · mcp__Claude_in_Chrome__browser_batch
468
Claude_in_Chrome · mcp__Claude_in_Chrome__computer
1.3k
Claude_in_Chrome · mcp__Claude_in_Chrome__file_upload
346
Claude_in_Chrome · mcp__Claude_in_Chrome__find
270
Claude_in_Chrome · mcp__Claude_in_Chrome__form_input
226
Claude_in_Chrome · mcp__Claude_in_Chrome__get_page_text
179
Claude_in_Chrome · mcp__Claude_in_Chrome__gif_creator
699
Claude_in_Chrome · mcp__Claude_in_Chrome__javascript_tool
336
Claude_in_Chrome · mcp__Claude_in_Chrome__list_connected_browsers
118
Claude_in_Chrome · mcp__Claude_in_Chrome__navigate
199
Claude_in_Chrome · mcp__Claude_in_Chrome__read_console_messages
448
Claude_in_Chrome · mcp__Claude_in_Chrome__read_network_requests
375
Claude_in_Chrome · mcp__Claude_in_Chrome__read_page
426
Claude_in_Chrome · mcp__Claude_in_Chrome__resize_window
211
Claude_in_Chrome · mcp__Claude_in_Chrome__select_browser
137
Claude_in_Chrome · mcp__Claude_in_Chrome__shortcuts_execute
249
Claude_in_Chrome · mcp__Claude_in_Chrome__shortcuts_list
169
Claude_in_Chrome · mcp__Claude_in_Chrome__switch_browser
151
Claude_in_Chrome · mcp__Claude_in_Chrome__tabs_close_mcp
182
Claude_in_Chrome · mcp__Claude_in_Chrome__tabs_context_mcp
237
Claude_in_Chrome · mcp__Claude_in_Chrome__tabs_create_mcp
98
Claude_in_Chrome · mcp__Claude_in_Chrome__upload_image
387
Claude_Preview · mcp__Claude_Preview__preview_click
147
Claude_Preview · mcp__Claude_Preview__preview_console_logs
192
Claude_Preview · mcp__Claude_Preview__preview_eval
218
Claude_Preview · mcp__Claude_Preview__preview_fill
146
Claude_Preview · mcp__Claude_Preview__preview_inspect
211
Claude_Preview · mcp__Claude_Preview__preview_list
71
Claude_Preview · mcp__Claude_Preview__preview_logs
235
Claude_Preview · mcp__Claude_Preview__preview_network
246
Claude_Preview · mcp__Claude_Preview__preview_resize
244
Claude_Preview · mcp__Claude_Preview__preview_screenshot
143
Claude_Preview · mcp__Claude_Preview__preview_snapshot
135
Claude_Preview · mcp__Claude_Preview__preview_start
256
Claude_Preview · mcp__Claude_Preview__preview_stop
88
computer-use · mcp__computer-use__computer_batch
805
computer-use · mcp__computer-use__cursor_position
89
computer-use · mcp__computer-use__double_click
221
computer-use · mcp__computer-use__hold_key
181
computer-use · mcp__computer-use__key
218
computer-use · mcp__computer-use__left_click
209
computer-use · mcp__computer-use__left_click_drag
249
computer-use · mcp__computer-use__left_mouse_down
135
computer-use · mcp__computer-use__left_mouse_up
121
computer-use · mcp__computer-use__list_granted_applications
82
computer-use · mcp__computer-use__middle_click
216
computer-use · mcp__computer-use__mouse_move
177
computer-use · mcp__computer-use__open_application
143
computer-use · mcp__computer-use__read_clipboard
67
computer-use · mcp__computer-use__request_access
565
computer-use · mcp__computer-use__request_teach_access
398
computer-use · mcp__computer-use__right_click
222
computer-use · mcp__computer-use__screenshot
216
computer-use · mcp__computer-use__scroll
232
computer-use · mcp__computer-use__switch_display
214
computer-use · mcp__computer-use__teach_batch
1.1k
computer-use · mcp__computer-use__teach_step
940
computer-use · mcp__computer-use__triple_click
221
computer-use · mcp__computer-use__type
140
computer-use · mcp__computer-use__wait
85
computer-use · mcp__computer-use__write_clipboard
83
computer-use · mcp__computer-use__zoom
282
dag-headroom · mcp__dag-headroom__dag_headroom
407
mcp-registry · mcp__mcp-registry__list_connectors
151
mcp-registry · mcp__mcp-registry__search_mcp_registry
298
mcp-registry · mcp__mcp-registry__suggest_connectors
403
scheduled-tasks · mcp__scheduled-tasks__create_scheduled_task
967
scheduled-tasks · mcp__scheduled-tasks__list_scheduled_tasks
161
scheduled-tasks · mcp__scheduled-tasks__update_scheduled_task
627


dag-headroom의 metric 출력

dag-headroom 세션 상태를 조회합니다.

dag-headroom: dag headroom 사용함
input: {"action":"status","session_id":"django-vs-spring-2026"}
{"session_id":"django-vs-spring-2026","dag":{"nodes":[{"name":"objective","thought_type":"Objective","status":"COMPLETED"},{"name":"language_ecosystem","thought_type":"Evidence","status":"COMPLETED"},{"name":"architecture_philosophy","thought_type":"Evidence","status":"COMPLETED"},{"name":"performance_scalability","thought_type":"Evidence","status":"COMPLETED"},{"name":"learning_productivity","thought_type":"Evidence","status":"COMPLETED"},{"name":"use_cases_community","thought_type":"Evidence","status":"COMPLETED"},{"name":"synthesis","thought_type":"Synthesis","status":"COMPLETED"}],"edges":[{"parent":"architecture_philosophy","child":"learning_productivity"},{"parent":"architecture_philosophy","child":"performance_scalability"},{"parent":"architecture_philosophy","child":"synthesis"},{"parent":"language_ecosystem","child":"performance_scalability"},{"parent":"language_ecosystem","child":"synthesis"},{"parent":"learning_productivity","child":"synthesis"},{"parent":"learning_productivity","child":"use_cases_community"},{"parent":"objective","child":"architecture_philosophy"},{"parent":"objective","child":"language_ecosystem"},{"parent":"performance_scalability","child":"synthesis"},{"parent":"performance_scalability","child":"use_cases_community"},{"parent":"use_cases_community","child":"synthesis"}]},"metrics":{"tokens_original":360,"tokens_compressed":360,"tokens_saved":0,"ratio":0},"restoration_manifest":{"how_to_restore":"dag_headroom(action='restore', session_id='<id>', ccr_hash='<hash>')","nodes":[{"name":"objective","type":"Objective","status":"COMPLETED","ccr_hash":"0b1e8a92f90a845e8bdbb6a5","restore_cmd":"dag_headroom(action='restore', session_id='django-vs-spring-2026', ccr_hash='0b1e8a92f90a845e8bdbb6a5')"},{"name":"language_ecosystem","type":"Evidence","status":"COMPLETED","ccr_hash":"867fe127ec50bd8356b7e5f7","restore_cmd":"dag_headroom(action='restore', session_id='django-vs-spring-2026', ccr_hash='867fe127ec50bd8356b7e5f7')"},{"name":"architecture_philosophy","type":"Evidence","status":"COMPLETED","ccr_hash":"4832831df399b5f43b82dad2","restore_cmd":"dag_headroom(action='restore', session_id='django-vs-spring-2026', ccr_hash='4832831df399b5f43b82dad2')"},{"name":"performance_scalability","type":"Evidence","status":"COMPLETED","ccr_hash":"38d06f1f9ca338617a542f77","restore_cmd":"dag_headroom(action='restore', session_id='django-vs-spring-2026', ccr_hash='38d06f1f9ca338617a542f77')"},{"name":"learning_productivity","type":"Evidence","status":"COMPLETED","ccr_hash":"1fb0039473987fb32b714b73","restore_cmd":"dag_headroom(action='restore', session_id='django-vs-spring-2026', ccr_hash='1fb0039473987fb32b714b73')"},{"name":"use_cases_community","type":"Evidence","status":"COMPLETED","ccr_hash":"6be0648ffbfadae988ad4c8c","restore_cmd":"dag_headroom(action='restore', session_id='django-vs-spring-2026', ccr_hash='6be0648ffbfadae988ad4c8c')"},{"name":"synthesis","type":"Synthesis","status":"COMPLETED","ccr_hash":"e8a34a0c64b00a112823faf7","restore_cmd":"dag_headroom(action='restore', session_id='django-vs-spring-2026', ccr_hash='e8a34a0c64b00a112823faf7')"}]}}
`

---

## dag-headroom Session Metrics — `django-vs-spring-2026`

### DAG 구조

```
objective
├── language_ecosystem ──────────┐
│                                ├──► performance_scalability ──┐
└── architecture_philosophy ─────┤                               ├──► synthesis
                                 └──► learning_productivity ────┤
                                       │                         │
                                       └──► use_cases_community ─┘
```

### 노드 현황

| 노드 이름 | 타입 | 상태 | CCR Hash |
|-----------|------|------|----------|
| `objective` | Objective | ✅ COMPLETED | `0b1e8a92` |
| `language_ecosystem` | Evidence | ✅ COMPLETED | `867fe127` |
| `architecture_philosophy` | Evidence | ✅ COMPLETED | `4832831d` |
| `performance_scalability` | Evidence | ✅ COMPLETED | `38d06f1f` |
| `learning_productivity` | Evidence | ✅ COMPLETED | `1fb00394` |
| `use_cases_community` | Evidence | ✅ COMPLETED | `6be0648f` |
| `synthesis` | Synthesis | ✅ COMPLETED | `e8a34a0c` |

### 압축(CCR) 메트릭

| 항목 | 값 |
|------|-----|
| 원본 토큰 | 360 |
| 압축 후 토큰 | 360 |
| 절약된 토큰 | 0 |
| 압축률 | 0% |

> **압축이 발생하지 않은 이유**: 각 노드의 payload가 80~1500자 범위 안에서 비교적 짧게 작성되었고, 세션 총량(360 토큰)이 CCR 압축 임계치에 도달하지 않았기 때문입니다. 노드가 더 많거나 payload가 클 경우 부모 컨텍스트가 CCR로 압축되어 토큰을 절약합니다.

### 엣지 (의존 관계)

총 **12개 엣지**, 7개 노드, 트리 깊이 4단계로 구성된 DAG였습니다.



=============================


/context


컨텍스트 창
41.3k / 200.0k (21%)
Messages
18.8k
9.4%
System tools
10.6k
5.3%
System prompt
6.7k
3.4%
Skills
3.3k
1.7%
MCP tools
2.0k
1.0%
MCP tools (deferred)
20.8k
10.4%
System tools (deferred)
12.1k
6.0%
Autocompact buffer
33.0k
16.5%
Free space
125.7k
62.8%

MCP 도구
22.7k
77
ccd_directory · mcp__ccd_directory__request_directory
173
ccd_session · mcp__ccd_session__dismiss_task
291
ccd_session · mcp__ccd_session__mark_chapter
329
ccd_session · mcp__ccd_session__spawn_task
776
ccd_session_mgmt · mcp__ccd_session_mgmt__archive_session
301
ccd_session_mgmt · mcp__ccd_session_mgmt__list_sessions
213
ccd_session_mgmt · mcp__ccd_session_mgmt__search_session_transcripts
209
ccd_session_mgmt · mcp__ccd_session_mgmt__send_message
259
Claude_in_Chrome · mcp__Claude_in_Chrome__browser_batch
468
Claude_in_Chrome · mcp__Claude_in_Chrome__computer
1.3k
Claude_in_Chrome · mcp__Claude_in_Chrome__file_upload
346
Claude_in_Chrome · mcp__Claude_in_Chrome__find
270
Claude_in_Chrome · mcp__Claude_in_Chrome__form_input
226
Claude_in_Chrome · mcp__Claude_in_Chrome__get_page_text
179
Claude_in_Chrome · mcp__Claude_in_Chrome__gif_creator
699
Claude_in_Chrome · mcp__Claude_in_Chrome__javascript_tool
336
Claude_in_Chrome · mcp__Claude_in_Chrome__list_connected_browsers
118
Claude_in_Chrome · mcp__Claude_in_Chrome__navigate
199
Claude_in_Chrome · mcp__Claude_in_Chrome__read_console_messages
448
Claude_in_Chrome · mcp__Claude_in_Chrome__read_network_requests
375
Claude_in_Chrome · mcp__Claude_in_Chrome__read_page
426
Claude_in_Chrome · mcp__Claude_in_Chrome__resize_window
211
Claude_in_Chrome · mcp__Claude_in_Chrome__select_browser
137
Claude_in_Chrome · mcp__Claude_in_Chrome__shortcuts_execute
249
Claude_in_Chrome · mcp__Claude_in_Chrome__shortcuts_list
169
Claude_in_Chrome · mcp__Claude_in_Chrome__switch_browser
151
Claude_in_Chrome · mcp__Claude_in_Chrome__tabs_close_mcp
182
Claude_in_Chrome · mcp__Claude_in_Chrome__tabs_context_mcp
237
Claude_in_Chrome · mcp__Claude_in_Chrome__tabs_create_mcp
98
Claude_in_Chrome · mcp__Claude_in_Chrome__upload_image
387
Claude_Preview · mcp__Claude_Preview__preview_click
147
Claude_Preview · mcp__Claude_Preview__preview_console_logs
192
Claude_Preview · mcp__Claude_Preview__preview_eval
218
Claude_Preview · mcp__Claude_Preview__preview_fill
146
Claude_Preview · mcp__Claude_Preview__preview_inspect
211
Claude_Preview · mcp__Claude_Preview__preview_list
71
Claude_Preview · mcp__Claude_Preview__preview_logs
235
Claude_Preview · mcp__Claude_Preview__preview_network
246
Claude_Preview · mcp__Claude_Preview__preview_resize
244
Claude_Preview · mcp__Claude_Preview__preview_screenshot
143
Claude_Preview · mcp__Claude_Preview__preview_snapshot
135
Claude_Preview · mcp__Claude_Preview__preview_start
256
Claude_Preview · mcp__Claude_Preview__preview_stop
88
computer-use · mcp__computer-use__computer_batch
805
computer-use · mcp__computer-use__cursor_position
89
computer-use · mcp__computer-use__double_click
221
computer-use · mcp__computer-use__hold_key
181
computer-use · mcp__computer-use__key
218
computer-use · mcp__computer-use__left_click
209
computer-use · mcp__computer-use__left_click_drag
249
computer-use · mcp__computer-use__left_mouse_down
135
computer-use · mcp__computer-use__left_mouse_up
121
computer-use · mcp__computer-use__list_granted_applications
82
computer-use · mcp__computer-use__middle_click
216
computer-use · mcp__computer-use__mouse_move
177
computer-use · mcp__computer-use__open_application
143
computer-use · mcp__computer-use__read_clipboard
67
computer-use · mcp__computer-use__request_access
565
computer-use · mcp__computer-use__request_teach_access
398
computer-use · mcp__computer-use__right_click
222
computer-use · mcp__computer-use__screenshot
216
computer-use · mcp__computer-use__scroll
232
computer-use · mcp__computer-use__switch_display
214
computer-use · mcp__computer-use__teach_batch
1.1k
computer-use · mcp__computer-use__teach_step
940
computer-use · mcp__computer-use__triple_click
221
computer-use · mcp__computer-use__type
140
computer-use · mcp__computer-use__wait
85
computer-use · mcp__computer-use__write_clipboard
83
computer-use · mcp__computer-use__zoom
282
dag-headroom · mcp__dag-headroom__dag_headroom
407
mcp-registry · mcp__mcp-registry__list_connectors
151
mcp-registry · mcp__mcp-registry__search_mcp_registry
298
mcp-registry · mcp__mcp-registry__suggest_connectors
403
scheduled-tasks · mcp__scheduled-tasks__create_scheduled_task
967
scheduled-tasks · mcp__scheduled-tasks__list_scheduled_tasks
161
scheduled-tasks · mcp__scheduled-tasks__update_scheduled_task
627


dag-headroom의 metric 출력

dag-headroom: dag headroom 사용함
input: {"action":"status","session_id":"django-vs-spring-001"}
{"session_id":"django-vs-spring-001","dag":{"nodes":[{"name":"objective","thought_type":"Objective","status":"COMPLETED"},{"name":"lang_ecosystem","thought_type":"Evidence","status":"COMPLETED"},{"name":"architecture","thought_type":"Evidence","status":"COMPLETED"},{"name":"philosophy","thought_type":"Evidence","status":"COMPLETED"},{"name":"performance","thought_type":"Evidence","status":"COMPLETED"},{"name":"learning_productivity","thought_type":"Evidence","status":"COMPLETED"},{"name":"pros_cons","thought_type":"Critique","status":"COMPLETED"},{"name":"use_cases","thought_type":"Evidence","status":"COMPLETED"},{"name":"synthesis","thought_type":"Synthesis","status":"COMPLETED"}],"edges":[{"parent":"architecture","child":"learning_productivity"},{"parent":"architecture","child":"performance"},{"parent":"architecture","child":"synthesis"},{"parent":"lang_ecosystem","child":"performance"},{"parent":"lang_ecosystem","child":"pros_cons"},{"parent":"learning_productivity","child":"pros_cons"},{"parent":"objective","child":"architecture"},{"parent":"objective","child":"lang_ecosystem"},{"parent":"objective","child":"philosophy"},{"parent":"performance","child":"pros_cons"},{"parent":"philosophy","child":"learning_productivity"},{"parent":"philosophy","child":"synthesis"},{"parent":"pros_cons","child":"synthesis"},{"parent":"pros_cons","child":"use_cases"},{"parent":"use_cases","child":"synthesis"}]},"metrics":{"tokens_original":501,"tokens_compressed":477,"tokens_saved":24,"ratio":0.0479},"restoration_manifest":{"how_to_restore":"dag_headroom(action='restore', session_id='<id>', ccr_hash='<hash>')","nodes":[{"name":"objective","type":"Objective","status":"COMPLETED","ccr_hash":"6e4acf5970472466586ad116","restore_cmd":"dag_headroom(action='restore', session_id='django-vs-spring-001', ccr_hash='6e4acf5970472466586ad116')"},{"name":"lang_ecosystem","type":"Evidence","status":"COMPLETED","ccr_hash":"1c566a8e98a21229702dc6bb","restore_cmd":"dag_headroom(action='restore', session_id='django-vs-spring-001', ccr_hash='1c566a8e98a21229702dc6bb')"},{"name":"architecture","type":"Evidence","status":"COMPLETED","ccr_hash":"3422b93c2d1365b9e525e0ed","restore_cmd":"dag_headroom(action='restore', session_id='django-vs-spring-001', ccr_hash='3422b93c2d1365b9e525e0ed')"},{"name":"philosophy","type":"Evidence","status":"COMPLETED","ccr_hash":"c9df4bcdaf55635c60afe58f","restore_cmd":"dag_headroom(action='restore', session_id='django-vs-spring-001', ccr_hash='c9df4bcdaf55635c60afe58f')"},{"name":"performance","type":"Evidence","status":"COMPLETED","ccr_hash":"39e368b360b17ef379692910","restore_cmd":"dag_headroom(action='restore', session_id='django-vs-spring-001', ccr_hash='39e368b360b17ef379692910')"},{"name":"learning_productivity","type":"Evidence","status":"COMPLETED","ccr_hash":"12ee8587cd01a86a9dfa004a","restore_cmd":"dag_headroom(action='restore', session_id='django-vs-spring-001', ccr_hash='12ee8587cd01a86a9dfa004a')"},{"name":"pros_cons","type":"Critique","status":"COMPLETED","ccr_hash":"db33c45ea6d63b2797f2302b","restore_cmd":"dag_headroom(action='restore', session_id='django-vs-spring-001', ccr_hash='db33c45ea6d63b2797f2302b')"},{"name":"use_cases","type":"Evidence","status":"COMPLETED","ccr_hash":"a3cb9091f576171869937f79","restore_cmd":"dag_headroom(action='restore', session_id='django-vs-spring-001', ccr_hash='a3cb9091f576171869937f79')"},{"name":"synthesis","type":"Synthesis","status":"COMPLETED","ccr_hash":"eb0b8fc59524bea09442ac7c","restore_cmd":"dag_headroom(action='restore', session_id='django-vs-spring-001', ccr_hash='eb0b8fc59524bea09442ac7c')"}]}}

### dag-headroom 세션 메트릭 — `django-vs-spring-001`

#### DAG 구조 (9노드)

| 노드 | 타입 | 상태 |
|------|------|------|
| `objective` | Objective | ✅ COMPLETED |
| `lang_ecosystem` | Evidence | ✅ COMPLETED |
| `architecture` | Evidence | ✅ COMPLETED |
| `philosophy` | Evidence | ✅ COMPLETED |
| `performance` | Evidence | ✅ COMPLETED |
| `learning_productivity` | Evidence | ✅ COMPLETED |
| `pros_cons` | Critique | ✅ COMPLETED |
| `use_cases` | Evidence | ✅ COMPLETED |
| `synthesis` | Synthesis | ✅ COMPLETED |

#### 압축(CCR) 메트릭

| 항목 | 값 |
|------|----|
| 원본 토큰 | 501 |
| 압축 후 토큰 | 477 |
| 절약 토큰 | **24** |
| 압축률 | 4.79% |

#### 엣지 구조 (의존 관계)

```
objective ──→ lang_ecosystem ──→ performance ──→ pros_cons ──→ synthesis
          ──→ architecture  ─┤                              ──→ use_cases ──→ synthesis
          ──→ philosophy   ──→ learning_productivity ──→ pros_cons
                           ──→ synthesis
```

이번 세션에서는 콘텐츠 자체가 비교적 짧아 압축률이 낮(4.79%)게 나왔습니다. CCR 압축은 노드 페이로드가 길어질수록 (1500자 근접) 더 높은 절약 효과를 보입니다.

