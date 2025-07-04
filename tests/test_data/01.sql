WITH RECURSIVE fixed_parts AS
  (SELECT d.document_id AS d,
          s.segment_id AS s,
          t1.token_id AS t1,
          t2.token_id AS t2,
          t3.token_id AS t3,
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
          s,
          t1,
          t2,
          t3,
          t3_lemma
   FROM fixed_parts) ,
               match_list AS
  (SELECT gather.d AS d,
          gather.s AS s,
          gather.t1 AS t1,
          gather.t2 AS t2,
          gather.t3 AS t3,
          gather.t3_lemma AS t3_lemma
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
