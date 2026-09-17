# Kho Báu Huyền Thoại: đặc tả hoàn thiện backend online từ APK

Ngày: 2026-09-17. Baseline: commit `990d8dc` trên `feat/native-game-entry`.
Trạng thái: đặc tả triển khai theo yêu cầu owner, chưa phải chứng nhận vận hành.

Tài liệu điều phối hiện hành:
[plan/task](../plans/2026-09-17-apk-online-backend-delivery.md),
[runbook](../runbooks/2026-09-17-apk-online-backend-delivery.md).
Bộ native-client-first trước đó giữ làm bằng chứng, không còn là hàng đợi việc.
Các yêu cầu DB/admin/tài chính của
[thiết kế 2026-09-16](2026-09-16-online-game-server-design.md) được kế thừa,
trừ các quy trình lab/test đã bị yêu cầu mới thay thế.

## 1. Kết quả cần giao

Backend thật phục vụ client native phục hồi: tài khoản, nhân vật, đội hình,
chiến đấu, thưởng, nâng cấp, vật phẩm, chiêu mộ, nhiệm vụ, bạn bè, mail, sự kiện;
admin có phân quyền và nhật ký; cấu hình phát hành online, backup và khôi phục.
Không dừng ở màn hình home hoặc ải 1-7; ải 1-7 là lát cắt đầu, không phải sản phẩm.

Giữ Python modular monolith, PostgreSQL và Pomelo codec hiện có. Worker xử lý
outbox; engine chỉ chạy module logic chiến đấu allowlist. Redis nếu cần chỉ giữ
presence/rate-limit, không giữ tài sản. Không đổi engine, viết lại client, chuyển
sang web demo, hoặc triển khai microservice cho từng route.

## 2. Chỉ thị thực thi mới

- Không dựng/chạy Lab, emulator, ADB, smoke vòng lặp hoặc seed tài khoản/vật phẩm.
- Không tạo task chỉ để tăng test count, không chạy broad suite/benchmark theo
  thói quen. Lần viết tài liệu này không chạy test hoặc thực hiện deploy.
- Mỗi task phải tạo code dùng thật, contract, migration hoặc artifact vận hành.
  Đọc nguồn, kiểm tra cú pháp/phạm vi diff/hash chỉ để bảo vệ thay đổi trực tiếp.
- Giữ nguyên test và bằng chứng cũ; không xóa để tạo trạng thái “xanh”. Các mục
  chưa thực thi phải ghi `NOT_RUN`, không suy ra đúng từ số test lịch sử.
- Nghiệm thu APK do owner thực hiện trên bản phát hành được chỉ định. Agent nhận
  lỗi/trace đã che thông tin rồi sửa đúng route, không tự điều khiển thiết bị.
- Triển khai hạ tầng công khai, migration DB thật và thanh toán thật là các
  quyết định riêng; lệnh viết plan không cấp quyền thực hiện những thay đổi đó.

## 3. Kiểm tra bộ tài liệu và code hiện tại

| Mục | Bằng chứng tại baseline | Việc phải sửa trong hàng đợi |
| --- | --- | --- |
| Auth/home/tutorial | native_auth.py, native_gateway.py, players/*; báo cáo native opening/tutorial | Giữ implementation; không xây lại tài khoản hoặc tutorial |
| Battle | battles/maps.py, settlement.py, engine.py; migration0016; prepare-native-battle.py | Plan cũ nói chưa có settlement/hook đã lỗi thời; hoàn thiện thay vì viết lại |
| Loot | content/native_battles.py chỉ chấp nhận `no-item-drops-v1` | Chưa có loot gameplay hợp lệ; không publish policy fixture thành luật thật |
| Stat | players/stats.py từ chối star khác1; bundle chuẩn bị cho ba role mở đầu | Mở rộng công thức/content trước khi mở roster/chiêu mộ/nâng sao |
| DB online | db/session.py chỉ nhận kbht_test/kbht_dev + loopback | Thêm profile production rõ ràng, không xóa kiểm tra an toàn cũ |
| Gateway online | CLI, native_gateway và metadata chỉ chấp nhận loopback | Tách bind nội bộ với endpoint công bố cho client và TLS |
| APK online | build-repacked.ps1 buộc cờ Lab cho patch native | Thêm profile online có endpoint allowlist; giữ source APK bất biến |
| Task3 cũ | Checkbox còn mở, artifact mới nằm cả trong SDD ignore | Đưa bằng chứng cần duy trì vào docs tracked; không dùng scratch làm phụ thuộc runtime |
| Route matrix | Nhiều trạng thái mô tả SQLite runner ngày16 | Tách backend PostgreSQL hiện tại khỏi lịch sử SQLite; không nâng status theo tên file |

## 4. Nguồn sự thật và quy tắc chưa biết

APK gốc SHA256:
`d61d4ae1994ec5bcafdcfaf2406cc88ed9611cbb65da853027799d50d6687eb4`.
`client-recovered/src/project.js` SHA256:
`9776b6e20978d5d911bc0abb85830820bac5a3bfb8db4e65a617c5d18646a818`.

Mỗi route đọc cả builder và consumer trong
`docs/protocol/vn-route-inventory.json`, `vn-core-consumers.json`, rồi đối chiếu
source thật. Mỗi luật ghi `apk-static`, `native-observed` hoặc
`owner-approved-new-rule`, source span, source hash và rules version.

Các quyết định còn thiếu không được ngầm mặc định:

| Quyết định | Tác động | Cách xử lý |
| --- | --- | --- |
| specifyDropValues125 và drop count0 | Loot, vật liệu nâng cấp, map reward | Truy ngược parser/consumer của drop; nếu APK không đủ thì lập proposal xác suất/quantity rõ và xin owner chọn; route phụ thuộc chưa được cấp thưởng |
| gem modulo10 so với EVERY_7 | Guarantee chiêu mộ | Ghi hai nguồn xung đột; version hóa quyết định trước khi bật paid/ten |
| power argument ngoài opening LV1 | Power/stat/chiến đấu | Giữ opening-v1 cho trạng thái cũ; mở rộng công thức có provenance, không nhân level tùy ý |
| thiếu config mode/event | Arena/guild/boss/event | Giao phục hồi contract/content theo nhóm; code500 cho route chưa đủ dữ liệu, không fake success |
| domain/host/TLS/secret reference | Triển khai thật | Owner cấp trước runbook activation; không tự chọn máy hoặc tài khoản cloud |
| điều kiện tiền thật/rút tiền | Finance | Chỉ record/audit với adapter disabled; chưa có luật thì không ghi tiền thật hoặc gọi provider |

Giữ `vn-data-api-observed-lookup-v1` cho đúng hai cặp hash đã ghi trong
`vn-native-battle-authority.md`; không biến nó thành luật last-wins toàn cục.
Không liên hệ endpoint nhà phát hành, SDK/payment/analytics lịch sử.

## 5. Ranh giới thực thi

APK -> form auth/Pomelo -> authenticated scope -> domain service -> PostgreSQL.
Domain transaction -> receipt + ledger + outbox -> worker. Admin gọi cùng domain
service với authority riêng, không gọi `logic.gmHandler` và không sửa JSON player.

Tái sử dụng `GameCommand`/`CommandResult` ở `contracts.py` và `UnitOfWork`/
`CommandExecutor` ở `db/uow.py`. Không tạo bộ command/economy thứ hai.
Command ID ổn định cho một thao tác, không lấy Pomelo request ID làm khóa bền vững.
Player/account/server lấy từ connector; dữ liệu client chỉ là yêu cầu, không phải
quyền sở hữu, giá, sát thương hoặc phần thưởng.

Envelope mở rộng được thương lượng phiên bản; legacy body vẫn giữ tên trường
`teamIndexs`, `bagIndexs`, `kindId`. Giữ `code/msg/_temp`, compressed player và
`player.update` đúng consumer. Receipt lưu nguyên response; cùng ID khác payload
phải conflict. Không tự retry thao tác trả tiền bằng command ID mới khi timeout.
Delta cũ không được ghi đè phiên bản mới; reconnect lấy snapshot và xử lý receipt
của thao tác đang chờ trước khi cho phép thao tác tiếp theo.

Transaction: xác thực -> khóa player theo ID tăng dần -> kiểm tra version,
release, ownership, giá/giới hạn -> ledger/tài sản/progress/claim/outbox/receipt
-> commit -> gửi response. Xác thực lại sau các lần chờ lock trước khi ghi.
Tính combat nặng ngoài lock; finalization kiểm tra lại battle/release/deadline.

## 6. Dữ liệu và tính toàn vẹn

Giữ migrations0001..0016, append revision mới sau HEAD thực tế. Không sửa lịch sử
migration đã apply. Không tạo lại native_owned_roles/native_role_equipment bằng
bảng mới chỉ vì tên trong thiết kế cũ khác code.

Wallet và inventory là số nguyên có ledger, balance không âm; system issuance/
sink đối ứng; nguồn reward unique. Role/equipment/skill/formation thuộc player,
không chấp nhận slot/kindId ngoài ownership. ID native phải JS-safe, player >10000.
Thời gian lưu UTC, business day Việt Nam: daily05:00, sign-in00:00, weekly Monday05:00.
Không chạy mass reset số dư lúc đổi ngày; counter/claim được khóa theo period key.

Content DRAFT/PUBLISHED bất biến, có source/rules/artifact hash. Player, battle và
receipt pin release. Release mới cần migration compatibility cho người chơi đã
lên cấp/có đồ; cutover hiện tại chỉ chấp nhận opening LV1 không được tái sử dụng
trên account đã tiến triển. Không rewrite report/receipt cũ khi repin.

## 7. Phạm vi gameplay theo thứ tự giao

1. Durable command bridge + snapshot đúng trạng thái hiện có.
2. Battle reward/content thật, 10106→10107→chapter2; không hạ độ khó để ép thắng.
3. Beli/AP/skill purchases; equipment LV/max/all; EXP/skill/evolve/star; vật liệu
   phải có nguồn kiếm được bằng gameplay, không command grant.
4. Single/ten recruitment, RNG outcome bền vững, duplicate conversion, guarantee.
5. Bag/use/sell/compose/shop, nguồn vật phẩm và consume/grant nguyên tử.
6. Task/achievement/sign-in/activity với progress từ event đã commit, claim một lần.
7. Bạn bè hai chiều/gifts, mail/gift code, profile và team đầy đủ.
8. Admin account/moderation/economy/content/liveops/audit và tài chính disabled.
9. Các route expansion thật trong inventory: mỗi mode đủ request/consumer,
   content, ownership, entry cost, report, reward và persistence trước khi mở UI.
10. Production profile, APK endpoint/TLS, release artifact, deploy/backup/runbook.

Mỗi nhóm vẫn phải xử lý validation, thiếu tiền/đồ, stale version, lặp command,
lock/expiry và release mismatch bằng lỗi native rõ ràng, không trả object rỗng.

## 8. Vận hành và an toàn phát hành

Runtime, migration, worker, content publisher, admin dùng DB role tách biệt.
Runtime không superuser/owner/DDL, không sửa ledger/audit đã commit. Production
config chỉ nhận endpoint/DB đã allowlist, secrets đọc từ file/store ngoài Git.
Reverse proxy TLS công khai HTTP/WebSocket; DB và raw listener là private.
Không tắt verify chứng chỉ nếu native TLS có vấn đề; sửa transport/profile.

Metrics: lỗi route, latency, active sessions, pending battle, settlement failures,
outbox lag, duplicate denial, ledger invariant, backup age. Log che token/password/
SDK keys; không log raw request auth hoặc player payload. Readiness chỉ true khi
schema/content/engine/release/DB role khớp; không dùng HTTP200 đơn thuần làm proof.

Backup mã hóa, WAL/PITR, mục tiêu RPO15phút/RTO60phút kế thừa thiết kế cũ; chưa đo
thì ghi `UNVERIFIED`, không quảng cáo SLA/capacity. Khôi phục là thao tác operator
được duyệt, không tự chạy drill/lab. Rollback app chỉ khi schema tương thích;
không restore DB cũ đè dữ liệu người chơi mới hoặc sửa lịch sử ledger.

## 9. Định nghĩa trạng thái giao hàng

`SOURCE_MAPPED`: đủ builder/consumer/luật có provenance.
`IMPLEMENTED`: domain + adapter + migration + release config đã nối.
`PACKAGED`: artifact/version/hash ghi nhận, chưa chứng minh runtime.
`OWNER_ACCEPTED`: owner xác nhận thao tác APK và persistence trên release cụ thể.
`BLOCKED_RULE`: thiếu đúng một luật được nêu tên; chuyển sang task độc lập khác.
`NOT_RUN`: chưa thực hiện; không gộp với passed hoặc accepted.

Không đổi các báo cáo native lịch sử thành kết quả mới. Commit source không
đồng nghĩa deploy; build/sign không đồng nghĩa boot; test cũ không đồng nghĩa
nghiệm thu online. Không có công bố “game hoàn chỉnh” khi route inventory còn
unsupported chưa được owner chấp nhận phạm vi.
