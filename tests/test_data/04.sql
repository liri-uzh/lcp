WITH RECURSIVE fixed_parts AS
  (SELECT "s"."char_range" AS "s_char_range",
          "s"."segment_id" AS "s",
          "tv"."char_range" AS "tv_char_range",
          "tv"."token_id" AS "tv",
          "tv"."xpos2" AS "tv_xpos2"
   FROM
     (SELECT Segment_id
      FROM bnc1.fts_vectorrest vec
      WHERE (vec.vector @@ '1dog'
             OR (vec.vector @@ '1a'
                 AND vec.vector @@ '1cat'
                 AND vec.vector @@ '1a <1> 1cat'))) AS fts_vector_s
   CROSS JOIN "bnc1"."tokenrest" "tv"
   CROSS JOIN "bnc1"."segmentrest" "s"
   WHERE "fts_vector_s"."segment_id" = "s"."segment_id"
     AND "s"."segment_id" = "tv"."segment_id"
     AND ("tv"."xpos2")::text = ('VERB')::text ),
               disjunction0 AS
  (SELECT fixed_parts."s" AS "s",
          fixed_parts."s_char_range" AS "s_char_range",
          fixed_parts."tv" AS "tv",
          fixed_parts."tv_char_range" AS "tv_char_range",
          fixed_parts."tv_xpos2" AS "tv_xpos2",
          jsonb_build_array(anonymous.Token_id) AS disjunction_matches
   FROM fixed_parts
   CROSS JOIN "bnc1"."tokenrest" "anonymous"
   CROSS JOIN "bnc1"."form" "anonymous_form"
   WHERE "anonymous_form"."form_id" = "anonymous"."form_id"
     AND "s" = "anonymous"."segment_id"
     AND ("anonymous_form"."form")::text = ('dog')::text
   UNION ALL SELECT fixed_parts."s" AS "s",
                    fixed_parts."s_char_range" AS "s_char_range",
                    fixed_parts."tv" AS "tv",
                    fixed_parts."tv_char_range" AS "tv_char_range",
                    fixed_parts."tv_xpos2" AS "tv_xpos2",
                    jsonb_build_array("anonymous3"."token_id", "anonymous4"."token_id") AS disjunction_matches
   FROM fixed_parts
   CROSS JOIN "bnc1"."tokenrest" "anonymous3"
   CROSS JOIN "bnc1"."tokenrest" "anonymous4"
   JOIN "bnc1"."form" "anonymous3_form" ON "anonymous3_form"."form_id" = "anonymous3"."form_id"
   JOIN "bnc1"."form" "anonymous4_form" ON "anonymous4_form"."form_id" = "anonymous4"."form_id"
   WHERE "s" = "anonymous3"."segment_id"
     AND ("anonymous3_form"."form")::text = ('a')::text
     AND "anonymous3_form"."form_id" = "anonymous3"."form_id"
     AND "s" = "anonymous4"."segment_id"
     AND ("anonymous4_form"."form")::text = ('cat')::text
     AND "anonymous4_form"."form_id" = "anonymous4"."form_id"
     AND "anonymous4"."token_id" - "anonymous3"."token_id" = 1),
               match_list AS
  (SELECT disjunction0."s" AS "s",
          disjunction0."s_char_range" AS "s_char_range",
          disjunction0."tv" AS "tv",
          disjunction0."tv_char_range" AS "tv_char_range",
          disjunction0."tv_xpos2" AS "tv_xpos2",
          disjunction0.disjunction_matches AS disjunction_matches
   FROM disjunction0),
               res1 AS
  (SELECT DISTINCT 1::int2 AS rstype,
                   jsonb_build_array(s, jsonb_build_array(tv, disjunction_matches))
   FROM match_list) ,
               res0 AS
  (SELECT 0::int2 AS rstype,
          jsonb_build_array(count(match_list.*))
   FROM match_list)
SELECT *
FROM res0
UNION ALL
SELECT *
FROM res1 ;