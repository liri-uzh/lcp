\c lcp_production lcp_production_owner

-- create functions as ROLE lcp_production_owner
-- security issues covered here: https://www.cybertec-postgresql.com/en/abusing-security-definer-functions/
REVOKE CREATE ON SCHEMA public FROM public;


CREATE OR REPLACE PROCEDURE main.open_import(
   temp_schema_hash  uuid
 , project_id        uuid
 , corpus_template   jsonb
)
AS $$
   DECLARE
      previous_version  int;
      corpus_name       text;
   BEGIN

      SELECT $3 -> 'meta' ->> 'name'
        INTO corpus_name
           ;

      ASSERT corpus_name IS NOT NULL AND corpus_name <> '', 'Could not find a name for the corpus in meta'
           ;

     EXECUTE format('CREATE SCHEMA %I AUTHORIZATION lcp_production_owner;', $1)
           ;
     EXECUTE format('GRANT ALL ON SCHEMA %I TO lcp_production_importer;', $1)
           ;

      SELECT corpus_id
        INTO previous_version
        FROM main.corpus
       WHERE corpus.name       = corpus_name
         AND corpus.project_id = $2
    ORDER BY current_version DESC
       LIMIT 1
           ;

      INSERT
        INTO main.inprogress_corpus (schema_path, corpus_id, project_id, corpus_template, status)
      SELECT $1
           , previous_version
           , $2
           , $3
           , 'ongoing'
           ;

   END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

ALTER PROCEDURE main.open_import
  SET search_path = pg_catalog,pg_temp;

REVOKE EXECUTE ON PROCEDURE main.open_import FROM public;
GRANT EXECUTE ON PROCEDURE main.open_import TO lcp_production_importer;


CREATE OR REPLACE FUNCTION main.finish_import(
   temp_schema_hash  uuid
 , schema_name       text
 , mapping_in        jsonb
 , token_counts_in   jsonb
 , sample_query_in   text
)
RETURNS table (
   project_id        main.corpus.project_id%TYPE
 , created_at        main.corpus.created_at%TYPE
 , corpus_id         main.corpus.corpus_id%TYPE
 , current_version   main.corpus.current_version%TYPE
 , enabled           main.corpus.enabled%TYPE
 , corpus_template   main.corpus.corpus_template%TYPE
 , description       main.corpus.description%TYPE
 , mapping           main.corpus.mapping%TYPE
 , name              main.corpus.name%TYPE
 , sample_query      main.corpus.sample_query%TYPE
 , schema_path       main.corpus.schema_path%TYPE
 , token_counts      main.corpus.token_counts%TYPE
 , version_history   main.corpus.version_history%TYPE
)
AS $$
   DECLARE
      next_version      int;
      new_schema_name   text;
      corpus_name       text;
      project_id_in     uuid;
      template          jsonb;
   BEGIN

      SELECT coalesce(max(cch.v), 0) + 1
        FROM (
             SELECT c.current_version AS v
               FROM main.corpus AS c
              WHERE c.schema_path ~ format('^%s_\d+', $2)
              UNION ALL
             SELECT (ch.initial_state).current_version AS v
               FROM main.corpus_history AS ch
              WHERE (ch.initial_state).schema_path ~ format('^%s_\d+', $2)
           ) cch
        INTO next_version;

      SELECT format('%s_%s', $2, next_version)
        INTO new_schema_name
           ;

      SELECT ipc.corpus_template
           , ipc.project_id
        INTO template
           , project_id_in
        FROM main.inprogress_corpus AS ipc
       WHERE ipc.schema_path = $1
           ;

      SELECT template -> 'meta' ->> 'name'
        INTO corpus_name
           ;

      ASSERT corpus_name IS NOT NULL AND corpus_name <> ''
           ;

     EXECUTE format('GRANT USAGE ON SCHEMA %I TO lcp_production_query_engine;', $1)
           ;

     EXECUTE format('ALTER SCHEMA %I RENAME TO %I;', $1, new_schema_name)
           ;

     EXECUTE format('REVOKE ALL ON SCHEMA %I FROM lcp_production_importer;', new_schema_name)
           ;

      UPDATE main.corpus AS mc
         SET enabled = FALSE
       WHERE mc.corpus_id = (
             SELECT ipc.corpus_id
               FROM main.inprogress_corpus AS ipc
              WHERE ipc.schema_path = $1
             )
           ;

      UPDATE main.inprogress_corpus AS ipc
         SET status = 'succeeded'
       WHERE ipc.schema_path = $1
           ;

      RETURN QUERY
      INSERT
        INTO main.corpus AS c (
               name
             , current_version
             , project_id
             , corpus_template
             , schema_path
             , mapping
             , token_counts
             , sample_query
             )
      SELECT corpus_name
           , next_version
           , project_id_in
           , template
           , new_schema_name
           , $3
           , $4
           , $5
   RETURNING c.project_id
           , c.created_at
           , c.corpus_id
           , c.current_version
           , c.enabled
           , c.corpus_template
           , c.description
           , c.mapping
           , c.name
           , c.sample_query
           , c.schema_path
           , c.token_counts
           , c.version_history
           ;
   END;
$$ LANGUAGE plpgsql SECURITY DEFINER;


ALTER FUNCTION main.finish_import
  SET search_path = pg_catalog,pg_temp;

REVOKE EXECUTE ON FUNCTION main.finish_import FROM public;
GRANT EXECUTE ON FUNCTION main.finish_import TO lcp_production_importer;


CREATE OR REPLACE PROCEDURE main.cleanup(
   temp_schema_hash  uuid
)
AS $$
   BEGIN

     EXECUTE format('DROP SCHEMA IF EXISTS %I CASCADE;', $1)
           ;

      UPDATE main.inprogress_corpus
         SET status = 'failed'
       WHERE schema_path = $1
           ;

   END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

ALTER PROCEDURE main.cleanup
  SET search_path = pg_catalog,pg_temp;

REVOKE EXECUTE ON PROCEDURE main.cleanup FROM public;
GRANT EXECUTE ON PROCEDURE main.cleanup TO lcp_production_importer;


-- TODO
-- CREATE OR REPLACE PROCEDURE main.grant_permissions(db_user text, schema_path, text)
-- AS $$
-- $$





CREATE TYPE main.meta_ops AS ENUM (
   'rename_layer'
 , 'rename_attribute'
);


CREATE OR REPLACE PROCEDURE main.change_meta(
   p_corpus_id      int
 , p_action         main.meta_ops
 , p_data           jsonb
)
AS $proc$
   DECLARE
      old_value   text;
      new_value   text;
      layer_name  text;
      selector    text[];
   BEGIN
      old_value := p_data ->> 'old';
      new_value := p_data ->> 'new';

       IF old_value IS NULL    THEN
         RAISE EXCEPTION 'no layer to rename specified. aborting.';
      ELSIF new_value IS NULL THEN
         RAISE EXCEPTION 'no new name specified. aborting.';
      ELSIF new_value ~ '"'   THEN
         RAISE EXCEPTION 'layer names cannot contain the ''"'' character. aborting.';
      ELSIF new_value ~ ''''  THEN
         RAISE EXCEPTION 'layer names cannot contain the "''" character. aborting.';
      END IF;

      CASE p_action
         WHEN 'rename_layer'
            THEN

               IF NOT new_value ~ '^[[:upper:]]' THEN
                  RAISE EXCEPTION 'layer names must start with uppercase letters. aborting.';
               END IF;

               IF NOT (
                  SELECT corpus_template
                           -> 'layer'
                       ? old_value
                    FROM main.corpus
                   WHERE corpus_id = p_corpus_id
               ) THEN
                  RAISE EXCEPTION 'layer "%" is not present. aborting.', old_value;
               END IF;

               selector := cast(format('{layer,%s}', old_value) AS text[]);

               UPDATE main.corpus
                  SET corpus_template = jsonb_set(
                           corpus_template #- selector
                         , cast(format('{layer,%s}', new_value) AS text[])
                         , corpus_template #> selector
                      )
                WHERE corpus_id = p_corpus_id
                    ;

               UPDATE main.corpus
                  SET mapping = jsonb_set(
                           mapping #- selector
                         , cast(format('{layer,%s}', new_value) AS text[])
                         , mapping #> selector
                      )
                WHERE corpus_id = p_corpus_id
                    ;

         WHEN 'rename_attribute'
            THEN

               layer_name := p_data ->> 'layer';

               IF layer_name IS NULL THEN
                  RAISE EXCEPTION 'no target layer specified. aborting.';
               ELSIF NOT new_value ~ '^[[:lower:]]' THEN
                  RAISE EXCEPTION 'attribute names must start with lowercase letters. aborting.';
               END IF;

               IF NOT (
                  SELECT corpus_template
                           -> 'layer'
                       ? layer_name
                    FROM main.corpus
                   WHERE corpus_id = p_corpus_id
               ) THEN
                  RAISE EXCEPTION 'layer "%" is not present. aborting.', layer_name;
               ELSIF NOT (
                  SELECT corpus_template
                           -> 'layer'
                           -> layer_name
                           -> 'attributes'
                       ? old_value
                    FROM main.corpus
                   WHERE corpus_id = p_corpus_id
               ) THEN
                  RAISE EXCEPTION 'attribute "%" is not present on layer "%". aborting.', old_value, layer_name;
               END IF;

               selector := cast(format('{layer,%s,attributes,%s}', layer_name, old_value) AS text[]);

               UPDATE main.corpus
                  SET corpus_template = jsonb_set(
                           corpus_template #- selector
                         , cast(format('{layer,%s,attributes,%s}', layer_name, new_value) AS text[])
                         , corpus_template #> selector
                      )
                WHERE corpus_id = p_corpus_id
                    ;

               IF (
                  SELECT mapping -> 'layer' -> layer_name -> 'attributes' ? old_value
                    FROM main.corpus
                   WHERE corpus_id = p_corpus_id
               ) THEN
                  UPDATE main.corpus
                     SET mapping = jsonb_set(
                              mapping #- selector
                            , cast(format('{layer,%s,attributes,%s}', layer_name, new_value) AS text[])
                            , mapping #> selector
                         )
                   WHERE corpus_id = p_corpus_id
                       ;
              END IF;

      END CASE;
   END
$proc$ LANGUAGE plpgsql SECURITY DEFINER;

ALTER PROCEDURE main.change_meta
  SET search_path = pg_catalog,pg_temp;

REVOKE EXECUTE ON PROCEDURE main.change_meta FROM public;
GRANT EXECUTE ON PROCEDURE main.change_meta TO lcp_production_importer;
