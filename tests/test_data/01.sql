WITH RECURSIVE fixed_parts AS
  (SELECT s.segment_id AS s,
          t1.token_id AS t1,
          t2.token_id AS t2,
          t3.token_id AS t3,
          t3_lemma.lemma AS t3_lemma
   FROM
     (SELECT Segment_id
      FROM bnc1.fts_vectorrest vec
      WHERE vec.vector @@ E'2true'
        AND vec.vector @@ E' 7ART <1> ( 2true &  7ADJ) <1>  7SUBST') AS s
   CROSS JOIN bnc1.document d
   CROSS JOIN bnc1.segmentrest has_char_range_3
   CROSS JOIN bnc1.tokenrest t1
   CROSS JOIN bnc1.tokenrest t2
   CROSS JOIN bnc1.lemma t3_lemma
   CROSS JOIN bnc1.tokenrest t3
   CROSS JOIN bnc1.lemma t2_lemma
   WHERE (d.meta ->> 'classCode')::text ~ '^S'
     AND d.char_range && has_char_range_3.char_range
     AND s.segment_id = has_char_range_3.segment_id
     AND s.segment_id = t1.segment_id
     AND t1.xpos2 = 'ART'
     AND s.segment_id = t2.segment_id
     AND ((t2_lemma.lemma)::text = 'true'
          AND t2.xpos2 = 'ADJ')
     AND s.segment_id = t3.segment_id
     AND t3.xpos2 = 'SUBST'
     AND t2.lemma_id = t2_lemma.lemma_id
     AND t2.token_id - t1.token_id = 1
     AND t3.token_id - t2.token_id = 1
     AND t3_lemma.lemma_id = t3.lemma_id ),
               gather AS
  (SELECT fixed_parts.s AS s,
          fixed_parts.t1 AS t1,
          fixed_parts.t2 AS t2,
          fixed_parts.t3 AS t3,
          fixed_parts.t3_lemma AS t3_lemma
   FROM fixed_parts) ,
               match_list AS
  (SELECT gather.s AS s,
          gather.t1 AS t1,
          gather.t2 AS t2,
          gather.t3 AS t3,
          gather.t3_lemma AS t3_lemma
   FROM gather),
               res0 AS
  (SELECT 0::int2 AS rstype,
          jsonb_build_array(count(*))
   FROM match_list) ,
               res1 AS
  (SELECT 1::int2 AS rstype,
          jsonb_build_array(s, jsonb_build_array(t1, t2, t3))
   FROM match_list) ,
               res2 AS
  (SELECT 2::int2 AS rstype,
          jsonb_build_array(t3_lemma, frequency)
   FROM
     (SELECT t3_lemma ,
             count(*) AS frequency
      FROM match_list
      GROUP BY t3_lemma) x)
SELECT *
FROM res0
UNION ALL
SELECT *
FROM res1
UNION ALL
SELECT *
FROM res2 ;
