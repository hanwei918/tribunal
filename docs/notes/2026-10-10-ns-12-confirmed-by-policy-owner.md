# POL-NS-12 confirmed by the policy owner (2026-10-10)

`policy/v3/amendments/0003-pol-ns-12.json` records `POL-NS-12` as approved by Zhou Hanwei on 2026-10-09, "to be
confirmed by Ji Guofang as policy owner", and revised the same day so that the rule states the geofence test in general
terms ("the distance to the pickup point and the speed at the arrival time") rather than quoting the sample's event
text. Ji Guofang, as policy owner, confirms that wording: the proposal at `policy/v3/proposals/0003-pol-ns-12.json`,
sha256 `79e597c05b69e6f213bed011df740b3819e4706899feacb76ac995cbcf61d97f`, the digest the amendment records.

The confirmation is recorded here and not in the amendment file, because `policy/` is frozen at `freeze-2026-10-09`
and an edit there would move the frozen tree.

Disclosed with it: the clause was drafted after the version-3 run of the organisers' sample (case 901) escalated,
and case 901 is the only case in the repository it reaches: two other cases carry a GPS_AUTO marker
(dev-v2 1703 and dev-v2-ext 2703), but neither records a `wait_timer_expired` event, which the clause requires.
