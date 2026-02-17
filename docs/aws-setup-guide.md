# AWS移行セットアップガイド

## 前提条件

- AWSアカウント作成済み
- AWS CLIインストール済み・設定済み（`aws configure`）
- Dockerインストール済み
- Herokuからのデータ移行は別途実施

---

## STEP 0: 事前準備 - AWSアカウントIDの確認

```bash
aws sts get-caller-identity --query Account --output text
```

出力された12桁の数字が`ACCOUNT_ID`。以降の手順では `123456789012` をご自身のIDに読み替えてください。

---

## STEP 1: {ACCOUNT_ID} を実際のIDに置換

`ecs/task-definition.json` と `ecs/iam-policies.json` 内のプレースホルダーを実際の値に置換します。

```bash
# Macの場合
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
sed -i '' "s/{ACCOUNT_ID}/${ACCOUNT_ID}/g" ecs/task-definition.json
sed -i '' "s/{ACCOUNT_ID}/${ACCOUNT_ID}/g" ecs/iam-policies.json

# Linuxの場合
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
sed -i "s/{ACCOUNT_ID}/${ACCOUNT_ID}/g" ecs/task-definition.json
sed -i "s/{ACCOUNT_ID}/${ACCOUNT_ID}/g" ecs/iam-policies.json
```

置換後に確認:

```bash
grep -n "ACCOUNT_ID" ecs/task-definition.json  # 何も出力されなければOK
```

---

## STEP 2: VPC / サブネット / Security Group / ALB / RDS / ECR を作成

### 2-1. VPCの作成

1. AWSコンソール → **VPC** → 「VPCを作成」
2. 以下を設定:

| 項目 | 値 |
|---|---|
| 作成するリソース | **VPCなど**（VPC+サブネット等を一括作成） |
| 名前タグの自動生成 | `medidocs` |
| IPv4 CIDR | `10.0.0.0/16` |
| アベイラビリティゾーン数 | **2** |
| パブリックサブネット数 | **2** |
| プライベートサブネット数 | **2** |
| NATゲートウェイ | **なし** |
| VPCエンドポイント | **なし** |

3. 「VPCを作成」をクリック

> 作成後、以下のリソースが自動生成されます:
> - VPC: `medidocs-vpc`
> - パブリックサブネット x 2（ALB・ECS用）
> - プライベートサブネット x 2（RDS用）
> - Internet Gateway（パブリックサブネット用）
> - ルートテーブル

---

### 2-2. Security Groupの作成

AWSコンソール → **VPC** → 「セキュリティグループ」→「セキュリティグループを作成」

#### sg-alb（ALB用）

| 項目 | 値 |
|---|---|
| セキュリティグループ名 | `medidocs-sg-alb` |
| 説明 | ALB - 院内固定IPからのHTTPS |
| VPC | 先ほど作成した `medidocs-vpc` |

**インバウンドルール:**

| タイプ | ポート | ソース | 説明 |
|---|---|---|---|
| HTTPS | 443 | `院内固定IP/32` | 院内からのHTTPS |
| HTTP | 80 | `院内固定IP/32` | HTTPSリダイレクト用 |

> 院内固定IPが複数ある場合はルールを追加。`/32` は単一IPを指す

**アウトバウンドルール:** デフォルトのまま（全許可）

---

#### sg-ecs（ECSタスク用）

| 項目 | 値 |
|---|---|
| セキュリティグループ名 | `medidocs-sg-ecs` |
| 説明 | ECS Fargateタスク |
| VPC | `medidocs-vpc` |

**インバウンドルール:**

| タイプ | ポート | ソース | 説明 |
|---|---|---|---|
| カスタムTCP | 8000 | `medidocs-sg-alb`（SGを選択） | ALBからのみ許可 |

**アウトバウンドルール:** デフォルトのまま（全許可）
> ECSタスクのパブリックIPによるBedrock等への外部通信はこのアウトバウンドで許可される

---

#### sg-rds（RDS用）

| 項目 | 値 |
|---|---|
| セキュリティグループ名 | `medidocs-sg-rds` |
| 説明 | RDS PostgreSQL |
| VPC | `medidocs-vpc` |

**インバウンドルール:**

| タイプ | ポート | ソース | 説明 |
|---|---|---|---|
| PostgreSQL | 5432 | `medidocs-sg-ecs`（SGを選択） | ECSタスクからのみ |

**アウトバウンドルール:** すべて削除（RDSはアウトバウンド不要）

---

### 2-3. RDS PostgreSQLの作成

AWSコンソール → **RDS** → 「データベースを作成」

| 項目 | 値 |
|---|---|
| 作成方法 | 標準作成 |
| エンジン | **PostgreSQL** |
| エンジンバージョン | PostgreSQL 16.x（最新） |
| テンプレート | **開発/テスト** |
| DBインスタンス識別子 | `medidocs-db` |
| マスターユーザー名 | `postgres` |
| マスターパスワード | （強力なパスワードを設定・記録しておく） |
| DBインスタンスクラス | **db.t4g.micro** |
| ストレージタイプ | **gp3** |
| ストレージ割り当て | `20` GB |
| ストレージの自動スケーリング | **無効**（コスト管理のため） |
| マルチAZ | **スタンバイなし（Single-AZ）** |
| VPC | `medidocs-vpc` |
| サブネットグループ | 「新規作成」→ **プライベートサブネットを選択** |
| パブリックアクセス | **なし** |
| セキュリティグループ | `medidocs-sg-rds` |
| データベース認証 | パスワード認証 |
| 最初のデータベース名 | `medidocs` |
| 自動バックアップ | **有効**（保持期間: 7日） |
| 暗号化 | **有効** |

「データベースを作成」をクリック（作成に約5分かかります）

> 作成後、「エンドポイント」に表示されるホスト名（例: `medidocs-db.xxxx.ap-northeast-1.rds.amazonaws.com`）をメモしておく

---

### 2-4. ECRリポジトリの作成

AWSコンソール → **Elastic Container Registry** → 「リポジトリを作成」

| 項目 | 値 |
|---|---|
| 可視性設定 | **プライベート** |
| リポジトリ名 | `medidocs-referral` |
| タグのイミュータビリティ | 無効 |
| プッシュ時にスキャン | 任意 |

「リポジトリを作成」をクリック

次に、ライフサイクルポリシーを設定して古いイメージを自動削除します:

1. 作成したリポジトリ → 「ライフサイクルポリシー」 → 「ルールを作成」
2. 以下を設定:

| 項目 | 値 |
|---|---|
| ルールの優先順位 | `1` |
| ルールの説明 | 最新10件以外を削除 |
| イメージのステータス | タグ付き |
| タグパターン | `*` |
| 一致条件 | イメージ数が `10` を超えた場合 |
| アクション | 期限切れ |

---

### 2-5. ACM証明書の取得

AWSコンソール → **Certificate Manager** → 「証明書をリクエスト」

> ⚠️ **必ず東京リージョン（ap-northeast-1）で作成すること**

| 項目 | 値 |
|---|---|
| 証明書タイプ | パブリック証明書 |
| ドメイン名 | `medidocsreferral.com` |
| 追加ドメイン名 | `*.medidocsreferral.com` |
| 検証方法 | **DNS検証** |

リクエスト後:
1. 証明書の詳細ページで「Route 53でレコードを作成」をクリック（検証用CNAMEレコードが自動作成される）
2. ステータスが「発行済み」になるまで待つ（5〜30分程度）

> Route 53でドメイン取得直後は「Route 53でレコードを作成」ボタンが表示される

---

### 2-6. Route 53でドメイン取得

AWSコンソール → **Route 53** → 「ドメインの登録」

1. `medidocsreferral.com` を検索して購入手続きを進める
2. 登録者情報（氏名・住所・電話番号）を入力
3. 購入完了後、自動的にホストゾーンが作成される（数分〜1時間程度）

---

### 2-7. ALBの作成

AWSコンソール → **EC2** → 「ロードバランサー」 → 「ロードバランサーを作成」 → **Application Load Balancer**

**基本設定:**

| 項目 | 値 |
|---|---|
| 名前 | `medidocs-alb` |
| スキーム | **インターネット向け** |
| IPアドレスタイプ | IPv4 |

**ネットワークマッピング:**

| 項目 | 値 |
|---|---|
| VPC | `medidocs-vpc` |
| AZ | ap-northeast-1a と ap-northeast-1c の**パブリックサブネット**を選択 |

**セキュリティグループ:** `medidocs-sg-alb` を選択

**リスナーとルーティング:**

まず、ターゲットグループを作成します（別タブで開く）:

- AWSコンソール → EC2 → 「ターゲットグループ」 → 「ターゲットグループを作成」
  - ターゲットタイプ: **IP アドレス**
  - ターゲットグループ名: `medidocs-tg-1`
  - プロトコル: HTTP / ポート: `8000`
  - VPC: `medidocs-vpc`
  - ヘルスチェックパス: `/health`
  - 「次へ」→ IPを登録せずに「ターゲットグループを作成」（ECSが自動登録）

ALB作成画面に戻り:

| リスナー | ポート | デフォルトアクション |
|---|---|---|
| HTTP | 80 | `medidocs-tg-1` へ転送（後でリダイレクトに変更） |
| HTTPS | 443 | `medidocs-tg-1` へ転送 |

HTTPS リスナーの「セキュリティリスナー設定」で:
- デフォルトSSL/TLS証明書: 先ほどACMで作成した `medidocsreferral.com` を選択

「ロードバランサーを作成」をクリック

**ALB作成後: アイドルタイムアウトを変更（SSE対応）**

1. 作成したALBの「属性」タブ → 「編集」
2. 接続アイドルタイムアウト: `120` 秒に変更（デフォルト60秒だとSSEが切断される）

**HTTP → HTTPSリダイレクトの設定:**

1. ALBの「リスナー」タブ → HTTP:80 → 「ルールの管理」
2. デフォルトルールを「リダイレクト」に変更:
   - プロトコル: HTTPS
   - ポート: 443
   - ステータスコード: 301

---

## STEP 3: IAMロールの作成

### 3-1. medidocsTaskRole（タスクロール）

AWSコンソール → **IAM** → 「ロール」 → 「ロールを作成」

| 項目 | 値 |
|---|---|
| 信頼されたエンティティタイプ | **AWSのサービス** |
| サービス | **Elastic Container Service** |
| ユースケース | **Elastic Container Service Task** |

「次へ」→ 権限ポリシーはこの画面では追加しない → ロール名 `medidocsTaskRole` → 「ロールを作成」

作成後、`medidocsTaskRole` ロールを開き → 「インラインポリシーを追加」:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "bedrock:InvokeModel",
        "bedrock:InvokeModelWithResponseStream"
      ],
      "Resource": "arn:aws:bedrock:ap-northeast-1::foundation-model/*"
    }
  ]
}
```

ポリシー名: `BedrockInvokePolicy`

---

### 3-2. ecsTaskExecutionRole（実行ロール）

同様に「ロールを作成」:

| 項目 | 値 |
|---|---|
| 信頼されたエンティティタイプ | **AWSのサービス** |
| サービス | **Elastic Container Service** |
| ユースケース | **Elastic Container Service Task** |

「次へ」→ 権限ポリシーで以下を検索して追加:
- `AmazonECSTaskExecutionRolePolicy`（ECR + CloudWatch Logs権限）

ロール名: `ecsTaskExecutionRole` → 「ロールを作成」

作成後、「インラインポリシーを追加」:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "secretsmanager:GetSecretValue"
      ],
      "Resource": "arn:aws:secretsmanager:ap-northeast-1:123456789012:secret:medidocs/*"
    }
  ]
}
```

> `123456789012` を実際のACCOUNT_IDに置換すること

ポリシー名: `SecretsManagerReadPolicy`

---

## STEP 4: Secrets Managerにシークレットを作成

AWSコンソール → **Secrets Manager** → 「新しいシークレットを保存する」

| 項目 | 値 |
|---|---|
| シークレットのタイプ | **その他のシークレットのタイプ** |
| シークレット名 | `medidocs/production` |

「キーと値のペア」で以下を追加（「+ キーと値のペアを追加」をクリックして1つずつ入力）:

| キー | 値 |
|---|---|
| `POSTGRES_HOST` | RDSのエンドポイント（例: `medidocs-db.xxxx.ap-northeast-1.rds.amazonaws.com`） |
| `POSTGRES_PORT` | `5432` |
| `POSTGRES_USER` | `postgres` |
| `POSTGRES_PASSWORD` | RDS作成時に設定したパスワード |
| `POSTGRES_DB` | `medidocs` |
| `POSTGRES_SSL` | `true` |
| `ANTHROPIC_MODEL` | 使用するモデルID（例: `anthropic.claude-3-5-sonnet-20241022-v2:0`） |
| `CSRF_SECRET_KEY` | 32文字以上のランダム文字列（下記コマンドで生成） |
| `CORS_ORIGINS` | `["https://medidocsreferral.com"]` |

**ランダム文字列の生成:**

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

「次へ」→「次へ」→「保存」

---

## STEP 5: CloudWatch Logsグループの作成

AWSコンソール → **CloudWatch** → 「ロググループ」 → 「ロググループを作成」

| 項目 | 値 |
|---|---|
| ロググループ名 | `/ecs/medidocs-referral` |
| 保持期間 | `30日`（コスト管理のため） |

「作成」をクリック

---

## STEP 6: ECSクラスター・タスク定義の登録

### 6-1. ECSクラスターの作成

AWSコンソール → **ECS** → 「クラスター」 → 「クラスターの作成」

| 項目 | 値 |
|---|---|
| クラスター名 | `medidocs-cluster` |
| インフラストラクチャ | **AWS Fargate（サーバーレス）** |

「作成」をクリック

---

### 6-2. タスク定義の登録

AWS CLIで登録します:

```bash
aws ecs register-task-definition \
  --cli-input-json file://ecs/task-definition.json \
  --region ap-northeast-1
```

成功すると以下のような出力が得られます:

```json
{
  "taskDefinition": {
    "taskDefinitionArn": "arn:aws:ecs:ap-northeast-1:123456789012:task-definition/medidocs-referral:1",
    "family": "medidocs-referral",
    ...
  }
}
```

AWSコンソールで確認: ECS → 「タスク定義」→ `medidocs-referral` が表示されればOK

---

### 6-3. ECSサービスの作成

AWSコンソール → **ECS** → `medidocs-cluster` → 「サービスを作成」

**環境:**

| 項目 | 値 |
|---|---|
| コンピューティングオプション | **起動タイプ** |
| 起動タイプ | **FARGATE** |

**デプロイ設定:**

| 項目 | 値 |
|---|---|
| サービスタイプ | **サービス** |
| タスク定義 | `medidocs-referral` |
| リビジョン | 最新（1） |
| サービス名 | `medidocs-referral-service` |
| 必要なタスク | `1` |

**ネットワーキング:**

| 項目 | 値 |
|---|---|
| VPC | `medidocs-vpc` |
| サブネット | **パブリックサブネット**（ap-northeast-1a と 1c） |
| セキュリティグループ | `medidocs-sg-ecs` |
| パブリックIP | **オン**（ENABLED） |

> ⚠️ パブリックIPをオンにしないとECSタスクがBedrock/ECRに通信できない

**ロードバランシング:**

| 項目 | 値 |
|---|---|
| ロードバランサーのタイプ | **Application Load Balancer** |
| ロードバランサー | `medidocs-alb`（既存を使用） |
| コンテナ | `medidocs-referral:8000:8000` |
| リスナー | 既存のリスナーを使用 → HTTPS:443 |
| ターゲットグループ | `medidocs-tg-1`（既存を使用） |

**ヘルスチェックの猶予期間:** `60` 秒

「サービスを作成」をクリック

> サービス作成後、タスクが起動し、ヘルスチェックが通過するまで3〜5分かかります

---

## STEP 7: 初回デプロイと動作確認

### 7-1. Dockerイメージをビルド・プッシュ

```bash
# ACCOUNT_IDを設定
export ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

# デプロイスクリプトを実行
chmod +x scripts/deploy.sh
./scripts/deploy.sh
```

または手動で:

```bash
export ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
export REGION="ap-northeast-1"

# ECRにログイン
aws ecr get-login-password --region ${REGION} | \
  docker login --username AWS --password-stdin ${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com

# Dockerイメージをビルド（Apple Siliconの場合は --platform linux/amd64 が必須）
docker build --platform linux/amd64 -t medidocs-referral .

# ECRにプッシュ
docker tag medidocs-referral:latest \
  ${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/medidocs-referral:latest
docker push ${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/medidocs-referral:latest

# ECSサービスを強制更新
aws ecs update-service \
  --cluster medidocs-cluster \
  --service medidocs-referral-service \
  --force-new-deployment \
  --region ${REGION}
```

---

### 7-2. 動作確認

**ヘルスチェックの確認:**

```bash
# ALBのDNS名を取得
ALB_DNS=$(aws elbv2 describe-load-balancers \
  --names medidocs-alb \
  --query 'LoadBalancers[0].DNSName' \
  --output text \
  --region ap-northeast-1)

echo "ALB DNS: ${ALB_DNS}"

# ヘルスチェック（院内ネットワークから実行）
curl -k https://${ALB_DNS}/health
# {"status": "healthy"} が返ればOK
```

**ECSタスクのログ確認:**

```bash
# 最新のログを確認
aws logs tail /ecs/medidocs-referral --follow --region ap-northeast-1
```

---

### 7-3. データ移行（Heroku PostgreSQL → RDS）

RDSはプライベートサブネットのため、踏み台EC2を経由します。

**踏み台EC2の作成（一時的）:**

1. AWSコンソール → EC2 → 「インスタンスを起動」
   - AMI: Amazon Linux 2023
   - インスタンスタイプ: t3.micro（無料枠）
   - ネットワーク: `medidocs-vpc` → **パブリックサブネット**
   - パブリックIPの自動割り当て: **有効**
   - セキュリティグループ: 自分のIPからSSH(22)許可
2. キーペアを作成・ダウンロード

**踏み台でPostgreSQLクライアントをインストール:**

```bash
# 踏み台EC2にSSH接続
ssh -i your-key.pem ec2-user@<踏み台のパブリックIP>

# PostgreSQLクライアントをインストール
sudo dnf install -y postgresql15
```

**RDSのSecurity Groupに踏み台SGからのアクセスを追加:**

- `medidocs-sg-rds` のインバウンドルールに PostgreSQL:5432 / 踏み台のSGまたはIP を追加

**Herokuからダンプ取得→RDSへ復元:**

ローカルマシンで:

```bash
# Herokuからダンプ取得
heroku pg:backups:capture --app your-heroku-app-name
heroku pg:backups:download --app your-heroku-app-name
# latest.dump がダウンロードされる

# ダンプを踏み台EC2に転送
scp -i your-key.pem latest.dump ec2-user@<踏み台のパブリックIP>:~/
```

踏み台EC2で:

```bash
# RDSに復元
pg_restore --verbose --clean --no-acl --no-owner \
  -h <RDSエンドポイント> \
  -U postgres \
  -d medidocs \
  latest.dump
# パスワード入力プロンプトが出たらRDSのパスワードを入力
```

**データ移行後: 踏み台EC2を停止・削除**（課金を止めるため）

---

### 7-4. Route 53でDNSを設定（本番切り替え）

AWSコンソール → **Route 53** → 「ホストゾーン」 → `medidocsreferral.com`

「レコードを作成」:

| 項目 | 値 |
|---|---|
| レコード名 | （空白 = ルートドメイン） |
| レコードタイプ | **A** |
| エイリアス | **オン** |
| トラフィックのルーティング先 | **Application Load Balancerと Classic Load Balancerへのエイリアス** |
| リージョン | `ap-northeast-1` |
| ロードバランサー | `medidocs-alb` を選択 |

「レコードを作成」をクリック

**Herokuカスタムドメインを削除（DNS切り替え後）:**

```bash
heroku domains:remove medidocsreferral.com --app your-heroku-app-name
```

---

### 7-5. 本番動作確認

ブラウザ（院内ネットワーク）で以下にアクセス:

- `https://medidocsreferral.com/health` → `{"status": "healthy"}`
- `https://medidocsreferral.com/` → メインページが表示される
- 要約生成機能でBedrock APIが正常動作することを確認
- SSEストリーミングが途中で切断されないことを確認
- 院内IP以外からのアクセスが拒否されることを確認（スマートフォンのモバイル回線等で確認）

---

## トラブルシューティング

### ECSタスクがSTOPPEDになる

```bash
# 停止理由を確認
aws ecs describe-tasks \
  --cluster medidocs-cluster \
  --tasks $(aws ecs list-tasks --cluster medidocs-cluster --query 'taskArns[0]' --output text) \
  --region ap-northeast-1 \
  --query 'tasks[0].stoppedReason'
```

### ヘルスチェックが通らない

- `sg-ecs` のインバウンドルールで `sg-alb` からポート8000が許可されているか確認
- CloudWatch Logsでアプリのエラーログを確認
- `POSTGRES_HOST` 等の環境変数がSecrets Managerで正しく設定されているか確認

### Bedrock APIエラー

- `medidocsTaskRole` に `bedrock:InvokeModel` 権限が付与されているか確認
- `AWS_REGION` が `ap-northeast-1` になっているか確認
- Bedrock コンソールでClaude 3.5 Sonnetが東京リージョンで有効化されているか確認
  - AWSコンソール → Amazon Bedrock → 「モデルアクセス」→ Claudeモデルを有効化

### ECRからイメージがプルできない

- ECSタスクのパブリックIPが有効になっているか確認（`assignPublicIp: ENABLED`）
- `ecsTaskExecutionRole` に `AmazonECSTaskExecutionRolePolicy` が付与されているか確認
