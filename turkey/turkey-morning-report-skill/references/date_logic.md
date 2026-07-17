# Date Logic

## Time Zones

- Turkey time (TR) = UTC+3 (no DST, fixed all year).
- Beijing time = UTC+8.
- TR = Beijing − 5 hours.

## Borsa İstanbul Trading Hours

- TR: 10:00–18:00
- Beijing: 15:00–23:00

## Market Holidays

Borsa İstanbul is closed on:

- Saturdays and Sundays
- Turkish public holidays (configurable in `config.json` under `holidays`)

Default public holidays configured:

- 2026-01-01 New Year's Day
- 2026-04-23 National Sovereignty and Children's Day
- 2026-05-01 Labour and Solidarity Day
- 2026-05-19 Commemoration of Atatürk, Youth and Sports Day
- 2026-07-15 Democracy and National Unity Day
- 2026-08-30 Victory Day
- 2026-10-29 Republic Day

## Target Date Resolution

The skill needs two dates:

- `today_date`: the current Turkish trading day, based on the system clock in TR time.
- `target_date`: the most recent completed trading day for which closing data exists.

### Rules

1. If the current TR time is before 10:00 on a trading day, the market has not yet opened. The most recent complete trading day is the previous calendar day.
2. If the current TR time is during market hours (10:00–18:00) or after, the current day is the trading day, but the closing review will only be available after ~18:30. For a morning briefing, the target date is still the previous calendar day.
3. If today is Saturday, the target date is Friday.
4. If today is Sunday, the target date is Friday.
5. If today is a public holiday, the target date is the most recent non-holiday trading day before it.
6. If the target date lands on a weekend or holiday, keep moving backward until a trading day is found.

### Examples

| Current TR date/time | today_date | target_date | Notes |
|----------------------|------------|-------------|-------|
| Mon 09:00 | Mon | Fri | Before market open, weekend skipped. |
| Mon 11:00 | Mon | Fri | Market open, but briefing uses Friday close. |
| Tue 09:00 | Tue | Mon | Before market open. |
| Tue 14:00 | Tue | Mon | Market open, briefing uses Monday close. |
| Wed 09:00 | Wed | Tue | Before market open. |
| Sat 10:00 | Sat | Fri | Weekend. |
| Sun 10:00 | Sun | Fri | Weekend. |
| Holiday Mon 10:00 | Holiday | Fri | Holiday is skipped. |
| Post-holiday Tue 09:00 | Tue | Fri | Long weekend. |

## Use in the Briefing

- The **title** of the briefing uses `today_date`.
- The **content** analyzes data from `target_date`.
- Example: a briefing generated on Monday morning is titled "2026-07-13" but discusses the Friday, 2026-07-10 closing review.

## Configuration

You can override the date logic in `config.json`:

```json
{
  "target_date": "auto"
}
```

Set `"target_date": "2026-07-10"` to force a specific date for testing or backfilling.
