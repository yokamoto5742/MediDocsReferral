# Bedrock 新モデルの利用規約同意手順（コンソール）

Amazon Bedrock で新しい Claude モデル（例: Claude Sonnet 5.5）を初めて使う際、アカウント単位で利用規約（AWS Marketplace の契約）への同意が必要です。
未同意のままアプリから呼び出すと、次のエラーになります。

```
Error code: 403 - {'message': 'anthropic.claude-sonnet-5-5 is not available for this account. ...'}
```

本書では、AWS マネジメントコンソールの Playground から 1 回呼び出すことで同意を完了させる手順を説明します。

## 前提条件

- 本番と同じ AWS アカウント（`149050210156`）にサインインできること
- 操作するユーザー/ロールに以下の権限があること（`AdministratorAccess` があれば可）
  - `bedrock:InvokeModel` / `bedrock:InvokeModelWithResponseStream`
  - `aws-marketplace:ViewSubscriptions` / `aws-marketplace:Subscribe`
- Anthropic モデルの利用目的フォーム（First-time use case）が提出済みであること
  - 未提出の場合は Playground 実行時に入力を求められるので、画面の指示に従って提出する

## 1. 現状を確認する（任意）

同意前の状態を確認しておきます。

```bash
aws bedrock get-foundation-model-availability --model-id anthropic.claude-sonnet-5-5 --region ap-northeast-1
```

`agreementAvailability.status` が `NOT_AVAILABLE` であれば、未同意の状態です。

## 2. Bedrock コンソールを開く

1. 管理者権限を持つユーザーで [AWS マネジメントコンソール](https://console.aws.amazon.com/) にサインインする
2. 画面右上のリージョンを **アジアパシフィック (東京) ap-northeast-1** に切り替える
   - アプリ（`AWS_REGION`）と同じリージョンで実行すること
3. **Amazon Bedrock** を開く

## 3. Playground でモデルを選択する

1. 左メニューの **Playgrounds**（または **Test**）から **Chat / Text** を開く
2. **Select model**（モデルを選択）をクリックする
3. 以下の順に選択する
   - Model provider: **Anthropic**
   - Model: **Claude Sonnet 5.5**
   - Inference（推論）: **Global cross-region inference**（`global.anthropic.claude-sonnet-5-5`）
     - 東京リージョンでは `jp.` プロファイルは未提供のため、`global` を選ぶ
4. **Apply**（適用）をクリックする

> コンソールの表記・メニュー位置は更新されることがあります。見つからない場合は Playground 内でモデル一覧から「Claude Sonnet 5.5」を探してください。

## 4. 1 回呼び出して同意する

1. プロンプト入力欄に任意の短い文（例: `こんにちは`）を入力する
2. **Run**（実行）をクリックする
3. 利用規約（EULA）や利用目的フォームの画面が表示された場合は、内容を確認して同意・送信する
4. モデルから応答が返れば、同意（Marketplace 購読）は完了です

> 同意は AWS アカウント単位で有効になります。一度完了すれば、ECS タスクロールなど同じアカウントの他のロールからも利用できます。

## 5. 同意の反映を確認する

```bash
aws bedrock get-foundation-model-availability --model-id anthropic.claude-sonnet-5-5 --region ap-northeast-1
```

`agreementAvailability.status` が `AVAILABLE` になっていれば完了です。反映まで数分かかる場合があります。

## 6. アプリで動作確認する

1. Secrets Manager の `medidocs/production` にある `ANTHROPIC_MODEL` が `global.anthropic.claude-sonnet-5-5` であることを確認する
2. アプリから Claude で文書を生成し、403 エラーが出ないことを確認する

## トラブルシューティング

| 症状 | 対処 |
|---|---|
| Playground でも 403 `not available for this account` | 利用目的フォームの提出状況を確認。解消しない場合は AWS サポートへ問い合わせ |
| `not authorized to perform aws-marketplace:Subscribe` | 操作ユーザーに Marketplace 権限を付与するか、管理者に実行を依頼 |
| `agreementAvailability` が `AVAILABLE` にならない | 数分待って再確認。長時間変わらない場合は [AWS Marketplace の購読管理](https://console.aws.amazon.com/marketplace/home#/subscriptions) で購読状態を確認 |
| 同意後もアプリだけ失敗する | `docs/iam-policies.json` の `medidocsTaskRole` の Bedrock 権限が IAM に反映されているか確認 |

## 参考: CLI で同意する場合

```bash
aws bedrock list-foundation-model-agreement-offers --model-id anthropic.claude-sonnet-5-5 --region ap-northeast-1
aws bedrock create-foundation-model-agreement --model-id anthropic.claude-sonnet-5-5 --offer-token <offerToken> --region ap-northeast-1
```
