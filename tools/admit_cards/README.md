# admit_cards

A small standalone helper for the Rajshahi board's public admit-card page: it loads one captcha per registration
number, you type them, and each admit card is saved as `<reg>.html`. Same idea as results-race, without the racing.

```sh
python3 app.py FIRST_REG LAST_REG --exam hsc --year 2026 --district rajshahi --out cards   # then open http://localhost:8000
python3 extract.py cards            # writes cards/students.json (roll + reg), ready for results-race
```

Standard library only. Saved cards contain students' personal data: keep them out of version control.
