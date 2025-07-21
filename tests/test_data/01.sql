WITH RECURSIVE fixed_parts AS
  (SELECT d.char_range AS d_char_range,
          d.document_id AS d,
          d.meta->'classcode' AS d_classcode,
          s.char_range AS s_char_range,
          s.segment_id AS s,
          t1.char_range AS t1_char_range,
          t1.token_id AS t1,
          t1.xpos2 AS t1_xpos2,
          t2.char_range AS t2_char_range,
          t2.token_id AS t2,
          t2.xpos2 AS t2_xpos2,
          t2_lemma.lemma AS t2_lemma,
          t3.char_range AS t3_char_range,
          t3.token_id AS t3,
          t3.xpos2 AS t3_xpos2,
          t3_lemma.lemma AS t3_lemma
   FROM
     (SELECT Segment_id
      FROM bnc1.fts_vectorrest vec
      WHERE vec.vector @@ '7ART <1> (2true & 7ADJ) <1> 7SUBST') AS fts_vector_s
   CROSS JOIN bnc1.document d
   CROSS JOIN bnc1.segmentrest s
   CROSS JOIN bnc1.tokenrest t1
   CROSS JOIN bnc1.tokenrest t2
   CROSS JOIN bnc1.tokenrest t3
   CROSS JOIN bnc1.lemma t3_lemma
   CROSS JOIN bnc1.lemma t2_lemma
   WHERE (d.meta->>'classCode')::text ~ '^S'
     AND d.char_range && s.char_range
     AND fts_vector_s.segment_id = s.segment_id
     AND s.segment_id = t1.segment_id
     AND (t1.xpos2)::text = ('ART')::text
     AND s.segment_id = t2.segment_id
     AND ((t2_lemma.lemma)::text = ('true')::text
          AND (t2.xpos2)::text = ('ADJ')::text)
     AND s.segment_id = t3.segment_id
     AND (t3.xpos2)::text = ('SUBST')::text
     AND t2.token_id - t1.token_id = 1
     AND t2_lemma.lemma_id = t2.lemma_id
     AND t3.token_id - t2.token_id = 1
     AND t3_lemma.lemma_id = t3.lemma_id ),
               gather AS
  (SELECT d,
          d_char_range,
          d_classcode,
          s,
          s_char_range,
          t1,
          t1_char_range,
          t1_xpos2,
          t2,
          t2_char_range,
          t2_lemma,
          t2_xpos2,
          t3,
          t3_char_range,
          t3_lemma,
          t3_xpos2
   FROM fixed_parts) ,
               match_list AS
  (SELECT gather.d AS d,
          gather.d_char_range AS d_char_range,
          gather.d_classcode AS d_classcode,
          gather.s AS s,
          gather.s_char_range AS s_char_range,
          gather.t1 AS t1,
          gather.t1_char_range AS t1_char_range,
          gather.t1_xpos2 AS t1_xpos2,
          gather.t2 AS t2,
          gather.t2_char_range AS t2_char_range,
          gather.t2_lemma AS t2_lemma,
          gather.t2_xpos2 AS t2_xpos2,
          gather.t3 AS t3,
          gather.t3_char_range AS t3_char_range,
          gather.t3_lemma AS t3_lemma,
          gather.t3_xpos2 AS t3_xpos2
   FROM gather),
               res1 AS
  (SELECT DISTINCT 1::int2 AS rstype,
                   jsonb_build_array(s, jsonb_build_array(t1, t2, t3))
   FROM match_list) ,
               res2 AS
  (SELECT 2::int2 AS rstype,
          jsonb_build_array(t3_lemma, frequency)
   FROM
     (SELECT t3_lemma ,
             count(*) AS frequency
      FROM match_list
      GROUP BY t3_lemma) x) ,
               res0 AS
  (SELECT 0::int2 AS rstype,
          jsonb_build_array(count(match_list.*))
   FROM match_list)
SELECT *
FROM res0
UNION ALL
SELECT *
FROM res1
UNION ALL
SELECT *
FROM res2 ;
