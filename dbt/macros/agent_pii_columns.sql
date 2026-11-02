-- Personal data by column: the stand-in for BigQuery policy tags (semantic/PLAN.md SL-22).
-- A column marked `meta: {pii: true}` is readable by the table's owner (the dbt user, which builds the
-- layers above it) and by the roles the model names in `config.meta.pii_readers` (the automation that acts on
-- the rows), and by no other role: every role holding SELECT on the whole relation, which is how an agent's
-- role reaches a dbt table (default privileges, agent_warehouse), keeps SELECT on its other columns only.
-- So `select *` and any query naming a personal column fail for an agent, and MetricFlow, which selects only
-- the columns a query needs, keeps working on a semantic model over such a table.
-- dbt rebuilds a relation on every run and its grants go with the old one, so every model of the project runs
-- agent_pii_columns() as a post-hook (dbt_project.yml), which renders nothing for a model without a personal
-- column; agent_warehouse re-applies it to the relations that exist after its schema-wide grants, so the order
-- in which the two first run does not matter.

-- The columns of a node (a graph node or the `model` context) marked personal data, under `config` or not.
{% macro pii_columns(node) -%}
  {% set found = [] %}
  {% for name, column in (node.get("columns") or {}).items() %}
    {% set meta = (column.get("config") or {}).get("meta") or column.get("meta") or {} %}
    {% if meta.get("pii") %}{% do found.append(name) %}{% endif %}
  {% endfor %}
  {{ return(found) }}
{%- endmacro %}

-- The roles that read a node's personal columns: `config.meta.pii_readers`.
{% macro pii_readers(node) -%}
  {% set meta = (node.get("config") or {}).get("meta") or node.get("meta") or {} %}
  {{ return(meta.get("pii_readers") or []) }}
{%- endmacro %}

-- The post-hook of every model (dbt_project.yml).
{% macro agent_pii_columns() -%}
  {% set pii = pii_columns(model) %}
  {% if pii and model.get("config", {}).get("materialized") != "ephemeral" %}
    {{ return(adapter.dispatch("agent_pii_grants")(this, pii, pii_readers(model))) }}
  {% endif %}
  {{ return("") }}
{%- endmacro %}

-- Postgres: column privileges. Roles that do not exist yet are skipped: agent_warehouse creates them and then
-- re-applies this to the relations that exist.
{% macro default__agent_pii_grants(relation, pii, readers) -%}
  {%- set rel = relation.include(database=False) -%}
do $pii$
declare
  target   regclass := to_regclass('{{ rel }}');
  personal name[] := array[{% for column in pii %}'{{ column }}'{{ "," if not loop.last }}{% endfor %}]::name[];
  readers  name[] := array[{% for role in readers %}'{{ role }}'{{ "," if not loop.last }}{% endfor %}]::name[];
  others   text;
  member   name;
begin
  if target is null then
    return;
  end if;
  select string_agg(quote_ident(attname), ', ' order by attnum) into others
    from pg_attribute
    where attrelid = target and attnum > 0 and not attisdropped and attname <> all (personal);
  for member in
    select distinct pg_get_userbyid(acl.grantee)
    from pg_class as c, aclexplode(c.relacl) as acl
    where c.oid = target and acl.privilege_type = 'SELECT'
      and acl.grantee not in (0, c.relowner)
      and pg_get_userbyid(acl.grantee) <> all (readers)
  loop
    execute format('revoke select on %s from %I', target, member);
    if others is not null then
      execute format('grant select (%s) on %s to %I', others, target, member);
    end if;
  end loop;
  foreach member in array readers loop
    if exists (select from pg_roles where rolname = member) then
      execute format('grant select on %s to %I', target, member);
    end if;
  end loop;
end
$pii$
{%- endmacro %}

-- BigQuery: the same columns carry `policy_tags` in the YAML, which dbt-bigquery writes with column-level
-- persist_docs; a reader is a Fine-Grained Reader on the tag, an IAM grant outside dbt
-- (docs/semantic-layer-on-bigquery.md, Who sees what).
{% macro bigquery__agent_pii_grants(relation, pii, readers) -%}
{%- endmacro %}

-- agent_warehouse's half: re-apply the column grants to every relation with a personal column that exists.
{% macro agent_pii_columns_existing() -%}
  {% for node in graph.nodes.values() | selectattr("resource_type", "equalto", "model") %}
    {% set pii = pii_columns(node) %}
    {% if pii and node.config.materialized != "ephemeral" %}
      {% set relation = adapter.get_relation(database=node.database, schema=node.schema, identifier=node.alias) %}
      {% if relation is not none %}
        {% do run_query(adapter.dispatch("agent_pii_grants")(relation, pii, pii_readers(node))) %}
      {% endif %}
    {% endif %}
  {% endfor %}
{%- endmacro %}
