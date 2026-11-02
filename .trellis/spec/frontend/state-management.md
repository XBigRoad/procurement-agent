# Review state

`ReviewSession` owns original quote/history/market paths, analysis date, weights,
authoritative result and downloadable bytes. Each session has an isolated dated
temporary folder. A new review replays cumulative changes against original inputs;
`create_review_template` preserves accepted changes for subsequent rounds.
