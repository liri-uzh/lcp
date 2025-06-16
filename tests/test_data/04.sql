WITH RECURSIVE fixed_parts AS
  (SELECT s.char_range AS s_char_range,
          s.segment_id AS s,
          tv.token_id AS tv
   FROM
     (SELECT Segment_id
      FROM bnc1.fts_vectorrest vec
      WHERE (vec.vector @@ '1dog'
             OR (vec.vector @@ '1a'
                 AND vec.vector @@ '1cat'
                 AND vec.vector @@ '1a <1> 1cat'))) AS fts_vector_s
   CROSS JOIN bnc1.segmentrest s
   CROSS JOIN bnc1.tokenrest tv
   WHERE fts_vector_s.segment_id = s.segment_id
     AND s.segment_id = tv.segment_id
     AND (tv.xpos2)::text = ('VERB')::text ),
               disjunction0 AS
  (SELECT fixed_parts.s AS s,
          fixed_parts.s_char_range AS s_char_range,
          fixed_parts.tv AS tv,
          jsonb_build_array(anonymous.Token_id) AS disjunction_matches
   FROM fixed_parts
   CROSS JOIN bnc1.tokenrest anonymous
   CROSS JOIN bnc1.form anonymous_form
   WHERE anonymous_form.form_id = anonymous.form_id
     AND s = anonymous.segment_id
     AND (anonymous_form.form)::text = ('dog')::text
   UNION ALL SELECT fixed_parts.s AS s,
                    fixed_parts.s_char_range AS s_char_range,
                    fixed_parts.tv AS tv,
                    jsonb_build_array(anonymous3.Token_id, anonymous4.Token_id) AS disjunction_matches
   FROM fixed_parts
   CROSS JOIN bnc1.tokenrest anonymous3
   CROSS JOIN bnc1.tokenrest anonymous4
   JOIN bnc1.form anonymous3_form ON anonymous3_form.form_id = anonymous3.form_id
   JOIN bnc1.form anonymous4_form ON anonymous4_form.form_id = anonymous4.form_id
   WHERE s_char_range && anonymous3.char_range
     AND (anonymous3_form.form)::text = ('a')::text
     AND anonymous3_form.form_id = anonymous3.form_id
     AND s_char_range && anonymous4.char_range
     AND (anonymous4_form.form)::text = ('cat')::text
     AND anonymous4_form.form_id = anonymous4.form_id
     AND anonymous4.Token_id - anonymous3.Token_id = 1),
               match_list AS
  (SELECT disjunction0.disjunction_matches AS disjunction_matches,
          disjunction0.s AS s,
          disjunction0.s_char_range AS s_char_range,
          disjunction0.tv AS tv
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