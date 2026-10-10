# pii-v1

Eight cases whose party text carries personal names, telephone numbers, e-mail addresses and vehicle plates, with place names that contain surnames as hard negatives. eval/answers/pii-v1/pii_spans.json lists, per case, every string that must be masked before display and every string that must not be.

Every telephone number starts 99, a block outside Singapore's allocated mobile ranges, and every e-mail domain is an RFC 2606 reserved name, so no string here identifies a real person. No government identifier of any kind is included.
