# SANDBOX_SPEC.md

此 sandbox 是一個 **單一 Linux container 環境**，內建多語言 toolchains 與常用 build 工具，目標是讓 LLM / Agent 可以在同一個工作區：

- 安裝 repo 依賴（例如 `npm install`, `bundle install`, `./gradlew test`）
- 編譯/建置可執行檔或 artifacts
- 執行單元測試 / 整合測試
- 透過 DB client 工具連線到外部 DB container（DB server 不在此 image 內）

---

## 2) 已安裝的語言與工具（可直接執行）

> 版本以 image build 時的 pin 為準；以下描述「此 image 會有什麼」與「行為邊界」。
>

### A. 系統與建置工具

- OS：Debian bookworm-slim
- 基礎工具：`bash`, `curl`, `git`, `ca-certificates`, `file`, `unzip`, `xz-utils`, `tzdata`
- 編譯/建置工具鏈：
    - `gcc`, `g++`, `make`（來自 `build-essential`）
    - `cmake`, `pkg-config`
    - `libc6-dev`
- Python（常用於測試/腳本）：`python3`, `python3-venv`, `pip`

### B. Node.js（含 npm + Corepack）

- 提供：`node`, `npm`
- 啟用：`corepack enable`
- Corepack 作用：提供 yarn/pnpm 等 **package manager binary proxies**，會依專案設定下載/執行正確版本的套件管理器。

> 用途：跑 Node 專案、React/TypeScript 前端專案的 install/build/test（如 `npm ci`, `npm test`, `pnpm i`, `yarn test`）。
>

### C. Go

- 提供：`go`, `gofmt`
- 用途：Go 專案 build/test（如 `go test ./...`, `go build ./...`）

### D. Java / Kotlin / Gradle

- 提供：OpenJDK 17（`java`, `javac`）
- `JAVA_HOME` 已設到 JDK 17 路徑
- 為什麼是 17：Gradle 執行本身需要 JVM 版本 **17–25**。

> 用途：執行 Kotlin/Gradle 專案（例如 `./gradlew test`, `./gradlew build`）。
>
>
> 注意：Kotlin compiler/Gradle 版本通常由 repo 的 wrapper 與 build scripts 決定，sandbox 不預裝 Gradle。
>

### E. Ruby + Bundler

- Ruby 以 `ruby-build` 從 source 安裝（固定版本 pin）
- 提供：`ruby`, `gem`, `bundler`
- `ruby-build` 定位：下載、編譯、安裝指定 Ruby 版本的工具。

> 用途：執行 Ruby/Rails repo 的依賴安裝與測試（如 `bundle install`, `bundle exec rake test`, `bundle exec rspec`）。
>
>
> 注意：Rails/相關 gems 由 repo 的 Gemfile / lockfile 決定；sandbox 不預裝 rails gem。
>

### F. Rust（rustup + cargo）

- 安裝方式：rustup（minimal profile）
- 提供：`rustup`, `cargo`, `rustc`
- toolchain/目錄：
    - `RUSTUP_HOME=/opt/rustup`
    - `CARGO_HOME=/opt/cargo`
    - `PATH` 內包含 `$CARGO_HOME/bin`
- rustup 支援透過 `RUSTUP_HOME` / `CARGO_HOME` 自訂安裝位置（避免寫到 user home）。

> 用途：Rust repo build/test（如 `cargo test`, `cargo build --release`）。
>

### G. DB client 工具（僅 client，非 server）

- Postgres client：`psql`（來自 `postgresql-client`）
- 另含 headers：`libpq-dev`（便於某些 native extensions / client 編譯）
- SQLite：`sqlite3` + `libsqlite3-dev`
- MySQL client：`default-mysql-client`

> 用途：測試/腳本需要時可直接用 client 連到 DB container；也能支援某些語言依賴在安裝時需要 DB headers 的情境。
>

---

## 3) PATH 與工具優先序（避免衝突）

此 sandbox 將主要語言工具放在不同路徑，並用明確 PATH 順序避免互相覆蓋：

1. Rust/Cargo：`/opt/cargo/bin`
2. Ruby：`/opt/ruby/bin`
3. Go：`/usr/local/go/bin`
4. Node：`/usr/local/bin`
5. 系統：`/usr/bin` 等

**預期效果：**

- 不會因 distro 自帶版本或其他安裝結果而「換到不同 toolchain」。
- `npm` 不會被 corepack 覆蓋；corepack 僅提供 yarn/pnpm 等 proxy binaries。

---

## 4) Sandbox 的邊界

### A. 不提供 DB server

此 image **不包含** `mongod` / `postgres` / `mysqld` 等資料庫 daemon。
你必須用 **docker compose** 或其他方式另外啟動 DB service container，並用連線字串指向該服務。
（sandbox 只提供 `psql`、mysql client、sqlite3 之類的 **client**。）

### B. 不預裝 repo 深層依賴

以下都不會在 image build 時預先安裝，必須在 container 內由 repo 自行安裝：
- Node：`node_modules`（`npm ci` / `pnpm i` / `yarn install`）
- Ruby：gems（`bundle install`）
- Go：modules（`go mod download` / `go test` 時自動抓）
- Kotlin/Gradle：Gradle wrapper 下載的 Gradle distributions、`~/.gradle` caches
- 任何額外系統套件（如 ImageMagick、playwright/chromium、特定 DB migration tool 等）

### C. 測試與執行腳本需要 repo 自帶或由你新增

sandbox 不替你生成：
- `docker-compose.yml`（DB services / ports / volumes）
- migration scripts / seed data
- test runner 設定（例如 UI tests、e2e tests）
- coverage 工具設定（尤其是 RAW SQL coverage 的規範/量測方式）
