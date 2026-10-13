{{ config(alias='tlc_green_trips', tags=['tlc']) }}

-- Green taxi trips: every landed row of every file version, canonical names and types (tlc_bronze).
-- data_month comes from the file name; silver picks the latest completed version per month.
{{ tlc_bronze('green') }}
