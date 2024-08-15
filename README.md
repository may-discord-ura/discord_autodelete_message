# discord_autodelete_message
指定したチャンネルのメッセージを一定期間で自動削除するbot

## 機能
- 指定チャンネルまたはスレッドのメッセージを一定時間経過したものから削除
  - ピン留めされたメッセージは削除しない
- 削除したメッセージをテキストファイルに出力

## 準備
### discord側の準備
- 開発者ポータルからbotを作成する
  - トークンを確保
  - `MESSAGE CONTENT INTENT`をオンにする
  - `Administrator`権限を付与するか、`Manage Messages`,`View Channels`を付与
### サーバーの設定
- 環境変数`TOKEN`にbotのトークンを入れておいてください
  - 面倒な場合は`main.py`最終行の`"TOKEN"`に直接トークンを入れる
### botの設定
- なし
  - 実行後、設定したいチャンネル内で`/auto_delete`を実行してください

## 実行
run main.py

## 備考
14日以上経過したメッセージは削除しない
