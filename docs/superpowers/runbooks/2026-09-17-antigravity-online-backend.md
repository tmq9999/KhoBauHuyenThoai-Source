# Antigravity: tiếp tục triển khai backend online Kho Báu Huyền Thoại

Đây là điểm vào dành cho Antigravity, không phải một plan mới.
Workspace: `D:\GeminiWorkspaceNew\KhoBauHuyenThoai`.
Nhánh bàn giao: `feat/native-game-entry`.
Baseline source: `990d8dc`; bộ spec/plan/runbook: `3757574`.
Hai commit đã được push lên repository private hiện tại.

## Prompt giao cho Antigravity

Copy nguyên khối sau vào conversation mới của Antigravity:

```text
Tiếp tục triển khai backend online game Kho Báu Huyền Thoại tại
D:\GeminiWorkspaceNew\KhoBauHuyenThoai, nhánh feat/native-game-entry.

Đọc AGENTS.md rồi đọc và làm theo:
docs/superpowers/runbooks/2026-09-17-antigravity-online-backend.md

Dùng installed Superpowers using-superpowers trước, rồi executing-plans.
Đây là yêu cầu thực hiện kế hoạch đã có, không yêu cầu viết lại plan hoặc chỉ
review tài liệu. Đọc spec/plan/runbook mà file bàn giao trỏ tới.

Kiểm tra git và progress để tiếp tục task đầu tiên chưa hoàn thành. Tại mốc
bàn giao3757574, bắt đầu T01 đối chiếu route/consumer/backend, rồi tiếp tục T02
durable native command bridge; sau đó thực hiện theo dependency của T03..T20.
Không làm lại auth/create/tutorial/settlement đã có. Không chỉ hoàn thành T01
rồi kết thúc khi T02 vẫn làm được trong phạm vi đã giao.

Cấm Lab, emulator, ADB, seed player/item, fake gameplay/auto-win và broad test
loops. Giữ các test/bằng chứng cũ, không xóa. Chỉ kiểm tra tĩnh/cú pháp/hash/diff
liên quan trực tiếp; runtime chưa chạy ghi NOT_RUN, không nhận là đã nghiệm thu.

Làm từ request builders VÀ response consumers của APK. Giữ PostgreSQL là nguồn
ghi duy nhất, tái sử dụng ledger/receipt/outbox, giữ source APK pinned bất biến.
Không đổi engine, không web demo, không quay về SQLite compatibility runner.

Mỗi task cập nhật progress tracked, README và CHANGELOG, ghi code đã giao và
điểm chưa nghiệm thu. Không dùng artifact chat hoặc .superpowers ignore làm
nguồn tiến độ duy nhất. Thiếu luật game thì ghi BLOCKED_RULE đúng route, nêu
quyết định cần owner và làm task độc lập còn lại; không bịa luật để vượt blocker.

Không deploy public, migrate DB thật, thao tác thiết bị, gọi provider hoặc tiền
thật khi chưa có chỉ định target/quyền riêng. Không force-push hay đổi visibility.
```

## 1. Đọc đúng bộ tài liệu

Sau `AGENTS.md`, đọc theo thứ tự:

1. [Spec hiện hành](../specs/2026-09-17-apk-online-backend-delivery.md): scope,
   authority, luật còn thiếu và giới hạn thực thi.
2. [Plan T01..T20](../plans/2026-09-17-apk-online-backend-delivery.md): task,
   file, interface, dependency và tiêu chí giao từng phần.
3. [Runbook thực thi/vận hành](2026-09-17-apk-online-backend-delivery.md): chu trình
   thực hiện, lệnh có sẵn so với CLI dự kiến, activation và ghi nhận kết quả.
4. [Progress tracked](../../agent-runs/online-server-progress.md): đọc checkpoint
   mới nhất trước, không lấy đoạn lịch sử dưới cùng làm next task.
5. `docs/protocol/vn-online-delivery-ledger.md` nếu đã được T01 tạo; nếu chưa có,
   đó là deliverable T01, không phải lỗi môi trường cần dựng Lab để sửa.

Khi sửa client build/loader/protocol, đọc thêm `client-recovered/README.md` và
báo cáo native recovery theo AGENTS. Bản runbook Antigravity ngày14 là tài liệu
reconstruction lịch sử, không phải hàng đợi backend online hiện tại.

## 2. Khôi phục trạng thái trước khi viết

Các lệnh read-only trong PowerShell tại workspace:

```powershell
git branch --show-current
git status --short
git log -5 --oneline
```

Nếu branch hoặc HEAD đã tiến xa hơn baseline, đọc commit/progress mới và giữ
thay đổi đó. Không checkout/reset về3757574, không clean ignored work, không
tạo lại các task đã được giao. Nếu worktree dirty, tách đúng file mình sở hữu;
không stage sửa đổi của agent khác vào commit của mình.

Trong Antigravity, dùng task artifact nếu công cụ hiện tại hỗ trợ để theo dõi
task đang làm. `manage_task` trong mapping CLI là quản lý process, không phải
checklist. Kiểm tra công cụ thực tế của phiên, không bịa tool theo tên ở Codex.
Luôn đồng bộ kết quả vào progress/route ledger trong repository để agent khác
có thể tiếp tục mà không có lịch sử chat. Nếu không có subagent thì thực thi
inline bằng executing-plans; không cài orchestrator chỉ để chạy task.

## 3. Điểm bắt đầu cụ thể

**T01:** đọc route inventory/core consumers, đối chiếu `NativeConnection.request`
trong `server-online/src/kbht_server/adapters/native_gateway.py` và handler domain.
Tạo ledger cho từng route: builder/consumer, handler, trạng thái PostgreSQL,
task chịu trách nhiệm, rule blocker. Phân biệt SQLite historical với PostgreSQL.
Chỉ sửa consumer profile khi đối chiếu source thật, không đánh implementation
theo tên file hoặc bằng chứng test cũ. Kết thúc T01 khi từng route có owner task
và handler/blocker, rồi chuyển T02; không viết thêm một kế hoạch tổng thể.

**T02:** đọc `contracts.py`, `db/uow.py`, native gateway, snapshot, socket wrapper
và các patch staged. Thực hiện capability/command ID/version/release/retry queue
theo task T02; giữ battleId protocol hiện có. Account/player/server lấy từ
connector, không từ body. Callback cũ không ghi đè state mới; timeout không tự
đổi ID để mua lại. Code server và client stage phải dùng cùng contract.

**Sau đó:** theo dependency của plan, không chờ deploy để viết gameplay. Thiếu
loot/guarantee/power rule thì ghi đúng câu hỏi quyết định, giữ route fail-closed và
làm task độc lập. Source settlement/hook đã có; nhiệm vụ là hoàn thiện các gap,
không dựng lại engine hoặc coi `no-item-drops-v1` fixture là reward thật.

## 4. Checkpoint bắt buộc trước khi hết phiên

Ghi vào `docs/agent-runs/online-server-progress.md`:

```text
Task đang làm / trạng thái:
File và hành vi đã thay đổi:
Source builder + consumer đã đối chiếu:
Kiểm tra thực sự đã chạy / phần NOT_RUN:
Rule hoặc quyền còn thiếu:
Commit nếu đã tạo / file chưa commit:
Bước tiếp theo chính xác (file, function, task):
```

Đánh checkbox chỉ cho công việc có bằng chứng tương ứng. `IMPLEMENTED` không
phải `OWNER_ACCEPTED`. Bàn giao phải chỉ ra next action cụ thể, không kết thúc
bằng “tiếp tục backend” hoặc tổng số test. Quy tắc commit/push và activation
theo runbook chung; file này không tự cấp thêm quyền remote/DB/device.
