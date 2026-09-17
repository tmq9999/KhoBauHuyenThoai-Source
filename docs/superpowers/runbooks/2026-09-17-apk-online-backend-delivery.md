# Runbook triển khai backend online Kho Báu Huyền Thoại

Ngày 2026-09-17. Baseline code `990d8dc`. Đây là runbook hiện hành theo yêu cầu
owner: thực hiện backend dựa trên APK, không Lab/emulator/ADB và không test vòng vo.

Đọc [spec](../specs/2026-09-17-apk-online-backend-delivery.md) và
[plan T01..T20](../plans/2026-09-17-apk-online-backend-delivery.md) trước khi sửa.
Không chạy lệnh trong runbook cũ chỉ vì một báo cáo lịch sử có nhắc đến nó.

## 1. Chế độ làm việc mặc định

Làm việc trên nhánh `feat/native-game-entry`, giữ nguyên dữ liệu và artifact cũ.
Khởi động bằng Superpowers `using-superpowers`, sau đó workflow của loại việc.
Không lặp brainstorming cho kiến trúc đã chốt; nếu thay engine/DB/protocol authority
thì phải nêu thay đổi và xin quyết định. Dùng Context7 khi cần cú pháp/API thư viện,
không mất thời gian tra docs cho việc chỉ đọc business logic của APK.

Lệnh kiểm tra trạng thái có sẵn, không khởi động dịch vụ:

```powershell
git branch --show-current
git status --short
git log -3 --oneline
```

Đọc task đầu tiên chưa hoàn thành trong plan và ledger tracked sau T01. Tại
baseline, bước tiếp theo là T01 đồng bộ route status rồi T02 command bridge,
không phải viết lại auth/create/tutorial hoặc build thêm APK Lab.

Giữ test cũ trong repository nhưng không chạy broad suites, benchmark, emulator,
ADB hoặc seed người chơi/vật phẩm. Không thay yêu cầu này bằng script “probe”
thực chất chạy lại cùng một lab flow. Khi chưa chạy thì ghi `NOT_RUN`.

## 2. Chu trình thực hiện một task

1. Đọc task, file domain hiện có và đúng request builder/response consumer của
   route. Không chỉ đọc `server-compatible` rồi sao chép luật sang PostgreSQL.
2. Ghi contract ngắn ngay cạnh tài liệu route: source hash/span, fields, authority,
   persisted state, cost/reward source, lỗi và merge behavior của client.
3. Viết production code vào module có trách nhiệm phù hợp. Tái sử dụng
   `GameCommand`, `CommandExecutor`, `UnitOfWork`, shared reward service và outbox.
4. Nếu thêm schema: kiểm tra HEAD file revision, append migration, cập nhật schema
   projection và role grants cùng task. Không apply lên DB thật trong bước code.
5. Kiểm tra trực tiếp phần thay đổi: đọc diff, cú pháp của file đã sửa, source pins
   nếu patch APK. Không chạy toàn bộ suite để thay cho việc đọc consumer.
6. Cập nhật route ledger, README và CHANGELOG. Ghi chính xác `IMPLEMENTED`,
   `BLOCKED_RULE` hoặc `NOT_RUN`; chỉ dùng `OWNER_ACCEPTED` khi có xác nhận thực.
7. Commit file theo task, không stage secrets/generated artifacts. Push đúng
   nhánh nếu còn nằm trong yêu cầu owner; không force push, không tự merge main.

Mỗi dòng ledger có cấu trúc:

```text
task | route | source builder/consumer | handler | migration/release |
status | unresolved rule | last commit | owner evidence reference
```

Checkpoint ngắn phải nói code gì đã đổi, người chơi được gì, thiếu gì. Không báo
“đã xong backend” chỉ từ syntax check hoặc source snapshot.

## 3. Khi vướng luật game

Với drop125/count0, guarantee recruitment, power ngoài opening hoặc mode thiếu
content: ghi source liên quan và ảnh hưởng chính xác; tạo proposal rule có version,
quantity/probability/cap/cost và provenance. Xin owner quyết định một lần ở đúng
chỗ cần thiết. Không dùng số0, empty list, auto-win hoặc fixture để vượt blocker.

Trong lúc chờ rule, làm task không phụ thuộc như production config/ops/admin
read-only. Không bật route mất phí trước khi biết reward. Không publish bản content
không thưởng rồi gọi đó là gameplay đã hoàn thiện.

## 4. Lệnh hiện có và giới hạn thật

Tại baseline, CLI có `migrate`, `check-invariants`, `import-content`,
`import-dependencies`, `prepare-equipment`, `audit-acquisition`, `read-content`,
`prepare-content`, `serve`, `serve-inventory`, `serve-bootstrap`, `serve-native`.
Tất cả chỉ có environment `test`/`development`; native endpoint còn loopback.
Đây không phải lệnh deploy production. Không đưa password superuser từ
`work/` vào runtime production và không dùng `serve-inventory` thay gateway game.

`build-repacked.ps1` hiện có NativeBattle nhưng buộc các Lab flags. Runbook này
không yêu cầu chạy nó. Task T18 phải tạo `-OnlineProfile` thực trước khi hướng dẫn
owner build artifact online. `.so` kèm APK vẫn là prebuilt native binary,
không được mô tả là C++ source đã phục hồi.

## 5. Giao diện vận hành cần triển khai, CHƯA phải lệnh sẵn dùng

Các lệnh dưới là **contract cho T17..T19**, chỉ dùng sau khi implementation và
`--help` thực tế đã khớp. Không copy chạy trên baseline. Không thêm behavior
migrate/publish ngầm vào `serve-native`.

| Giao diện dự kiến | Trách nhiệm | Ghi dữ liệu? |
| --- | --- | --- |
| `kbht-server release inspect --profile FILE --manifest FILE` | kiểm tra config/hash/schema/role/content, in thông tin đã che | Không |
| `kbht-server release prepare --profile FILE --manifest FILE` | import/stage DRAFT source/content đã duyệt | Có, DRAFT only |
| `kbht-server migrate --profile FILE --revision REV --approve-target ID` | additive migration bằng migrator, đúng DB đã xác nhận | Có |
| `kbht-server release activate --profile FILE --manifest FILE --expected-release UUID --approve-target ID` | maintenance/drain, compatibility check, đổi release nguyên tử | Có |
| `kbht-server serve-native --profile FILE --manifest FILE` | runtime non-owner, đúng bind/advertise, không seed/migrate/publish | Chỉ gameplay đã authorize |
| `kbht-server worker --profile FILE` | outbox lease, retry/backoff, consumer dedup | Có, worker ACL |
| `kbht-server ops status --profile FILE` | schema/release/queue/health, sanitized output | Không |
| `kbht-server ops backup-plan --profile FILE` | hiển thị target/retention/encryption/WAL requirement | Không |
| `kbht-server ops backup --profile FILE --approve-target ID` | backup encrypted và manifest, không in credentials | Tạo backup |
| `kbht-server ops restore-plan --profile FILE --backup FILE --target ID` | kiểm tra target khác active DB, thời điểm và compatibility | Không |
| `kbht-server ops restore --profile FILE --backup FILE --target ID --approve-target ID` | restore đúng đích được duyệt, không tự đổi active target | Có |

`ID` ở đây là identifier của target trong private profile, không phải giá trị
đoán được từ tên database. CLI phải so khớp expected target/release, fail nếu
profile thiếu, hostname không allowlist, manifest mismatch hoặc wrong role.

Online builder contract dự kiến của T18:

```text
build-repacked.ps1 -OnlineProfile FILE -NativeAvailability -NativeBattle -Sign
```

Profile phải chứa command capability T02; NativeBattle không thay command retry
cho các route mua/nâng cấp. Key material/password chỉ qua private secret reference.
Builder không install, launch, upload APK hoặc publish manifest tự động.

## 6. Đầu vào owner cần cấp trước triển khai thật

Đây là checklist của activation, không phải blocker cho việc viết code:

- Repository commit và release scope/routes được phép mở.
- Target host/cloud/project, operator identity và phạm vi quyền triển khai.
- Domain auth/metadata/gate/connector, TLS certificate reference và DNS ownership.
- PostgreSQL database/schema/host, migration/runtime/worker/admin/publisher secret
  references; không gửi mật khẩu vào chat/Git.
- Signing identity APK, nơi phân phối APK/manifest riêng và người được nhận.
- Content/rules approvals, đặc biệt loot và recruitment; release trước để kiểm tra.
- Backup location/encryption/retention, maintenance window và rollback operator.
- Nếu chuyển dữ liệu cũ: nguồn backup được phép đọc, mapping/reconciliation và
  danh sách player bị ảnh hưởng. Mặc định không import SQLite tự động.

Thiếu host/domain/quyền thì kết quả là package/config-ready, không phải online.
Không tự tạo hạ tầng trả phí hoặc hạ TLS xuống HTTP để tránh xin đầu vào.

## 7. Trình tự phát hành được duyệt

Chỉ thực hiện sau khi owner chỉ định target và yêu cầu activation cụ thể.
Đây không phải chỉ thị chạy ngay trong phiên viết tài liệu.

1. **Đóng gói:** ghi app Git SHA, lockfile hash, engine/module hash, APK/manifest
   hashes, schema revision, content/rules IDs và protocol capabilities. Chỉ dùng
   artifacts cùng release; không reuse manifest của build khác.
2. **Kiểm tra read-only:** release inspect so profile/DB role/schema/version/engine;
   missing dependency là fail closed, không tạo user/server/content tự động.
3. **Bảo toàn dữ liệu:** operator tạo backup đã duyệt, ghi manifest và vị trí WAL;
   backup chưa thực hiện ghi NOT_RUN. Không dùng db dump chứa secret làm git artifact.
4. **Maintenance/drain:** chặn fresh paid mutations, chờ admitted transaction,
   freeze active battles theo policy deadline, ngừng worker có lease an toàn.
5. **Migration:** additive theo revision target, account migrator riêng; lỗi thì
   dừng và giữ maintenance, không sửa alembic_version bằng tay để bỏ qua.
6. **Content:** prepare DRAFT, kiểm tra provenance/closure và compatibility với
   tất cả player state; activate bằng expected previous release. Old receipts,
   battle reports và ownership history không đổi pin ngầm.
7. **Service:** chạy app/worker runtime role; raw listeners/DB private, proxy TLS
   public theo allowlist, advertised endpoints trỏ đúng domain. Readiness fail thì
   không chuyển ingress sang release mới.
8. **Artifact:** owner phân phối APK đúng signing identity/manifest. Agent không
   install/launch trên thiết bị hoặc mở emulator. Không ép người dùng clear data.
9. **Xác nhận:** owner đi flow cần giao và cung cấp observed result/sanitized trace;
   chỉ route thực sự xác nhận được đánh OWNER_ACCEPTED. Lỗi quay về task đúng route.
10. **Ghi nhận:** docs/release/online-release-status.md ghi target pseudonym,
    artifact hashes, changed routes, accepted/unrun/blocked, backup reference và
    rollback constraints. Không lưu token, password, session raw hoặc SDK keys.

## 8. Bộ tiêu chí owner nghiệm thu, không phải lab/test script

| Luồng thực tế | Kết quả cần thấy |
| --- | --- |
| Login/create/relog | đúng account/server/player, state bền; không duplicate starter |
| Home/team | integer power, không undefined/NaN; owned roles/stats thống nhất |
| Battle10106→10107→chapter2 | thắng/thua theo engine; reward/XP/AP/attempt/progress bền |
| Mất kết nối khi trả kết quả | thao tác đã commit chỉ thu phí/thưởng một lần |
| Equipment/skills/EXP/evolve | cost/material đúng source, full role update, relog không mất |
| Recruitment single/ten | lượt mới khác retry, starter không lặp, duplicate/guarantee đúng policy |
| Shop/bag/use/sell/compose | giá/stock/source thật, tombstone và balance nhất quán |
| Tasks/sign-in/events | đủ điều kiện mới claim, không lặp sau relog/reset |
| Friends/gifts | hai tài khoản đồng nhất quan hệ, AP gift một lần |
| Mail/gift code | eligibility/recipient đúng, reward một lần, unread thực |
| Admin | role giới hạn thật, reason/approval/audit, không trực tiếp sửa wallet |
| Finance | disabled rõ cho adapter chưa duyệt; không hiển thị đã thanh toán giả |

Nếu owner không chạy một mục, giữ NOT_RUN; không thay bằng test service hoặc
ảnh màn hình boot. Không buộc owner làm lại luồng không bị thay đổi để kéo dài task.

## 9. Xử lý sự cố

- **Auth/reconnect lỗi:** xác định route/consumer, release/capability và lỗi đã
  che; không log password/token để tìm lỗi. Không đổi uid thành authority.
- **Reward sai/double charge:** maintenance mutation liên quan, bảo toàn receipt/
  ledger/report; đọc source ID. Sửa bằng compensation được duyệt, không DELETE ledger.
- **Battle parity sai:** giữ seed/actions/team/content/engine hash để đối chiếu;
  chưa xác định nguyên nhân không sửa client star hoặc ép server thắng.
- **Migrate lỗi:** giữ maintenance, không apply revision tiếp theo; phục hồi hoặc
  roll-forward do operator quyết định sau đọc transaction/schema thực tế.
- **App release lỗi:** rollback app chỉ khi schema/content compatible. Sau khi
  đã có writes mới không restore backup cũ đè progression; cần reconciliation.
- **Rule thiếu:** route explicit unavailable, ghi BLOCKED_RULE và chuyển task độc lập.

Backup/restore thực tế chỉ chạy trên đích operator duyệt, không tổ chức drill lab
tự động. Mục tiêu RPO/RTO/capacity chưa đo phải ghi UNVERIFIED.

## 10. Git và bàn giao mỗi đợt

Chỉ stage file nguồn/tài liệu task; các `work/`, secrets, key, DB, APK generated
đang ignore giữ nguyên local. Snapshot `990d8dc` đã push lên repo private theo lệnh
owner; điều đó không cấp quyền công khai raw APK/source hoặc secret lịch sử.

```powershell
git diff --check
git diff --stat
git status --short
```

Sau staged review và commit, push thường lên nhánh hiện tại rồi so SHA:

```powershell
git push origin feat/native-game-entry
git rev-parse HEAD
git ls-remote --heads origin refs/heads/feat/native-game-entry
```

Không force-push hoặc sửa lịch sử để xử lý remote conflict. Commit/push có thể
hoàn thành dù runtime còn NOT_RUN; báo rõ hai trạng thái riêng. Mọi delivery
commit cập nhật README/CHANGELOG, không gắn nhãn “production ready” cho snapshot.
