{{ config(tags=['migration']) }}

-- The gate of the migration rehearsal (semantic/PLAN.md SL-11): one row per problem with a consumer
-- (an exposure carrying meta.migration, migration/consumers.yml) that reads its new model:
--   - a field of migration.parity differs and its owner has not accepted it (meta.migration.accepted),
--   - migration.parity has no row for it,
--   - a consumer of an earlier kind (dashboard, then agent, then automation) still reads legacy.
-- Every consumer reads exactly one of its two relations. Reading legacy needs no check: it is the
-- state before the switch, and rolling back to it is always allowed.
{%- set parity = ref('parity') %}
{%- set kinds = ['dashboard', 'agent', 'automation'] %}
{%- set string = dbt.type_string() %}
{%- set checks = [] %}
{%- if execute %}
  {%- set consumers = [] %}
  {%- for exposure in graph.exposures.values() | sort(attribute='name') %}
    {%- set migration = (exposure.config.meta or {}).get('migration') or (exposure.meta or {}).get('migration') %}
    {%- if migration %}
      {%- set reads = exposure.depends_on.nodes %}
      {%- set on_new = ('model.' ~ project_name ~ '.' ~ migration.new) in reads %}
      {%- set on_legacy = ('model.' ~ project_name ~ '.' ~ migration.legacy) in reads %}
      {%- do consumers.append({'name': exposure.name, 'kind': migration.kind, 'on_new': on_new,
                               'accepted': (migration.accepted or {}).keys() | list}) %}
      {%- if migration.kind not in kinds %}
        {%- do checks.append("select '" ~ exposure.name ~ "', 'kind " ~ migration.kind ~ " is not one of " ~ kinds | join(', ') ~ "'") %}
      {%- endif %}
      {%- if on_new == on_legacy %}
        {%- do checks.append("select '" ~ exposure.name ~ "', 'reads " ~ ('both' if on_new else 'neither') ~ " of " ~ migration.legacy ~ " and " ~ migration.new ~ "'") %}
      {%- endif %}
    {%- endif %}
  {%- endfor %}
  {%- for consumer in consumers if consumer.on_new %}
    {%- set accepted = consumer.accepted | map('string') | list %}
    {%- do checks.append(
      "select consumer, field || ' differs on ' || cast(keys_differing as " ~ string ~ ") || ' keys, not accepted' from " ~ parity
      ~ " where consumer = '" ~ consumer.name ~ "' and status = 'differs'"
      ~ (" and field not in ('" ~ accepted | join("', '") ~ "')" if accepted else '')) %}
    {%- do checks.append(
      "select '" ~ consumer.name ~ "', 'no rows in migration.parity' from (select count(*) as n from " ~ parity
      ~ " where consumer = '" ~ consumer.name ~ "') as p where n = 0") %}
    {%- for earlier in consumers if not earlier.on_new and earlier.kind in kinds and consumer.kind in kinds
        and kinds.index(earlier.kind) < kinds.index(consumer.kind) %}
      {%- do checks.append("select '" ~ consumer.name ~ "', 'switched before " ~ earlier.kind ~ " " ~ earlier.name ~ "'") %}
    {%- endfor %}
  {%- endfor %}
{%- endif %}

-- The first branch names the columns and is never a problem; each check adds one branch.
select consumer, problem
from (
    select cast(null as {{ string }}) as consumer, cast(null as {{ string }}) as problem
    {%- for check in checks %}
    union all
    {{ check }}
    {%- endfor %}
) as problems
where consumer is not null
