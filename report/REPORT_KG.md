# Báo cáo Day 19 — Flat RAG vs GraphRAG

**Họ tên:**Nguyễn Danh Gia Minh  **MSSV:** 2A202602441  **Ngày:** 05-10-2026

> Kỳ vọng và thang điểm: `SUBMISSION.md`. Mọi số liệu phải khớp với `ket_qua_benchmark_kg.txt`. Bản thiết kế ontology nộp riêng ở `report/ONTOLOGY.md`.

## 1. Chi phí (10 điểm)

Dán 2 bảng `Indexing` và `Querying` từ `ket_qua_benchmark_kg.txt`:

```
== Indexing (one-off)
pipeline  calls    in_tok  out_tok       USD  seconds
flat        176     56072        0   0.00112     48.9
graph       196     91958     4538   0.00923    121.9

== Querying (mean per question)
pipeline  recall  judge   in_tok  out_tok       USD  seconds
flat        0.43   1.00      694       47   0.00013     1.33
graph       0.89   1.33     4149       88   0.00067     2.63
```

| Chỉ số | Flat | Graph | Graph / Flat |
| --- | --- | --- | --- |
| Indexing USD | 0.00112 | 0.00923 | ×8.24 |
| Indexing giây | 48.9 | 121.9 | ×2.49 |
| Mỗi câu: USD | 0.00013 | 0.00067 | ×5.15 |
| Mỗi câu: giây | 1.33 | 2.63 | ×1.98 |
| Mỗi câu: in_tok | 694 | 4149 | ×5.98 |

**Chi phí tăng thêm đến từ đâu?** (2–3 câu)
> Indexing Graph có 20 lần gọi thêm (196 so với 176) để trích xuất cấu trúc từ tin, làm chi phí tăng từ $0.00112 lên $0.00923 và thời gian từ 48.9 lên 121.9 giây. Khi hỏi, Graph đưa thêm fact graph vào prompt: input trung bình tăng từ 694 lên 4,149 token/câu, kéo chi phí/câu lên ×5.15 và thời gian lên ×1.98. Theo số đo này Graph không hòa vốn về tiền chỉ nhờ hỏi nhiều hơn, vì chi phí biến đổi mỗi câu cũng cao hơn; phần tăng chỉ hợp lý khi cần câu trả lời xuyên KB.

## 2. Từng câu hỏi (10 điểm)

| Câu | Loại | Flat recall / judge | Graph recall / judge | Thắng | Vì sao (1 câu) |
| --- | --- | --- | --- | --- | --- |
| Q1 | single-hop-law | 1.00 / 2 | 1.00 / 2 | Hòa | Cả hai tìm được định nghĩa tiền chất; Graph thêm viện dẫn Điều 2 khoản 4. |
| Q2 | single-hop-news | 1.00 / 2 | 1.00 / 2 | Hòa | Cả hai nêu đủ hai người lãnh án tử hình; Graph thêm tội danh và Điều 251. |
| Q3 | cross-kb | 0.00 / 0 | 0.67 / 1 | Graph (một phần) | Graph nối được Điều luật và khung cơ bản nhưng trả nhầm 24 tháng thay vì 36 tháng. |
| Q4 | cross-kb | 0.00 / 0 | 0.67 / 1 | Graph (sai mức tối đa) | Graph nối đúng hành vi và Điều 255 nhưng chỉ đưa khung khoản 1, bỏ sót khoản 4. |
| Q5 | cross-kb-multi-hop | 0.60 / 1 | 1.00 / 1 | Graph (recall; còn sai luật) | Graph nêu khoản 4 và loại hình phạt nhưng nói ngưỡng 5 kg thay vì ngưỡng MDMA 100 g. |
| Q6 | aggregation | 0.00 / 1 | 1.00 / 1 | Graph (recall) | Graph nêu đủ các tên/vụ bắt buộc; hai pipeline cùng được judge chấm một phần. |

## 3. Phân tích lỗi (20 điểm)

Chọn ít nhất 2 nhóm lỗi trong E1–E6 (`LAB_GUIDE.md` Bước 8.4). Sao chép khung dưới đây cho mỗi lỗi.

### Lỗi E2: Thiếu ngữ cảnh luật cho câu hỏi về mức phạt tối đa

- **Hiện tượng:** GraphRAG trả lời Hoàng Nato có mức phạt tối đa 07 năm, nhưng Điều 255 khoản 4 quy định phạt tù 20 năm hoặc tù chung thân.
- **Bằng chứng:** `ket_qua_benchmark_kg.txt`, Q4 Graph, `recall=0.67 judge=1`: “Giang hồ 'Hoàng Nato' bị bắt về hành vi tổ chức sử dụng trái phép chất ma túy. Hành vi này có thể bị phạt tù tối đa 07 năm theo Điều 255 Bộ luật Hình sự.”

```cypher
MATCH (k:Case)-[:CHARGED_WITH]->(c:Crime)
WHERE c.name CONTAINS 'tổ chức sử dụng'
RETURN k.name AS case_name, c.name AS crime
LIMIT 8;

MATCH (:Article {id:'Điều 255 BLHS'})-[:HAS_CLAUSE]->(cl:Clause)
RETURN cl.number AS clause, cl.penalty AS penalty
ORDER BY clause;
```

```
Neo4j (rút gọn kết quả):
- Có vụ "Vụ bắt giang hồ 'Hoàng Nato' và 126 người liên quan 8 đường dây ma túy"
  nối với tội "tổ chức sử dụng trái phép chất ma túy".
- Điều 255 khoản 1: phạt tù từ 02 năm đến 07 năm.
- Điều 255 khoản 4: phạt tù 20 năm hoặc tù chung thân.
```

- **Nguyên nhân:** `Neo4jGraph.context` chỉ luôn lấy khoản 1 và các khoản có `MENTIONS` chất của vụ. Điều 255 khoản 4 không có quan hệ `MENTIONS` chất; nhánh lấy khoản cao nhất chỉ chạy khi câu hỏi ghi thẳng số Điều, trong khi Q4 không ghi số Điều. Vì vậy prompt không nhận được khoản 4 dù node luật có trong graph.
- **Đề xuất sửa:** khi câu hỏi có ý “tối đa/cao nhất”, lấy khoản có số lớn nhất từ Điều luật tìm được qua tội danh của vụ (và lấy điều luật liên quan nếu câu hỏi không nói rõ Điều). Thêm test Q4 đảm bảo context chứa “20 năm hoặc tù chung thân”. Đánh đổi: thêm một truy vấn/điều kiện Cypher và có thể tăng số fact, nhưng sẽ không kết luận mức tối đa chỉ từ khoản cơ bản.

### Lỗi E4: Recall và LLM judge bất đồng

- **Hiện tượng:** Q6 Flat được `recall=0.00` nhưng `judge=1` (đúng một phần); hai phép đo đánh giá câu trả lời khác nhau.
- **Bằng chứng:** `ket_qua_benchmark_kg.txt`, Q6 Flat:

```
recall=0.00 judge=1
Cả ba vụ việc trong tin tức đều có liên quan đến ma túy MDMA. Cụ thể:
1. Vụ việc của Đức liên quan đến số viên nén hình tam giác màu hồng - xám được xác định là MDMA.
2. Vụ việc của Thành liên quan đến 5 viên nén màu trắng được xác định là ma túy MDMA.
3. Vụ việc của Đông liên quan đến 0,686g ma túy MDMA được thu giữ trong buồng chữa bệnh.
```

Q6 trong `data/benchmark_kg.json` yêu cầu `must_include` ba chuỗi `Cái Quang Huy`, `Lê Minh Thành`, `Pháp y tâm thần`. Câu trả lời trên không chứa nguyên văn chuỗi nào nên recall bằng 0; judge lại chấm 1/2. Điểm judge không kèm lý do trong file kết quả, nên không thể xác định chỉ từ log vì sao judge đánh giá một phần.

- **Nguyên nhân:** recall là phép đếm khớp chuỗi chính xác, còn judge là đánh giá ngữ nghĩa bằng LLM; hai cách đo có thang điểm và độ ổn định khác nhau. Câu trả lời cũng gọi người/vụ bằng dạng rút gọn (“Đức”, “Thành”, “Đông”), nên không đạt các chuỗi bắt buộc dù có mô tả một số nội dung liên quan MDMA.
- **Đề xuất sửa:** giữ recall để đo các ý bắt buộc nhưng đối chiếu thủ công với gold và nguồn; bổ sung đánh giá entity/alias có kiểm chứng thay vì chỉ substring, đồng thời lưu lý do của judge trong kết quả. Đánh đổi: cần duy trì alias/rubric và có thể tốn thêm chi phí gọi judge; không nên thay recall hoàn toàn bằng một điểm LLM không giải thích.

## 4. Kết luận (5 điểm)

Khi nào nên dùng KG, khi nào Flat RAG là đủ? Dẫn số liệu ở mục 1–2.
> Với câu hỏi đơn bước, có dữ kiện tập trung trong một đoạn/bài như Q1–Q2, Flat RAG là đủ: cả hai đạt recall 1.00 và judge 2. Với câu hỏi cần nối tin–luật hoặc tổng hợp nhiều vụ (Q3–Q6), Graph recall lần lượt là 0.67, 0.67, 1.00, 1.00, so với Flat 0.00, 0.00, 0.60, 0.00. Tuy vậy lỗi Q3–Q5 cho thấy recall cao không đảm bảo câu trả lời đúng luật hoặc đúng mức án. Trong phép đo này Graph tốn ×8.24 chi phí indexing, ×5.15 chi phí mỗi câu và gần ×6 input token; nên dùng khi khả năng truy vấn quan hệ nhiều bước có giá trị, đồng thời kiểm chứng fact/pháp lý, chứ không thay Flat mặc định cho mọi câu.

## 5. Tự kiểm (5 điểm)

```
$ pytest tests/ -q
51 passed (đã chạy sau khi hoàn thiện KG-4)

$ python bench_kg.py --check
Chưa chạy trong phiên này: lệnh gọi graph.reset() và xóa graph Neo4j hiện có trước khi dựng lại.
```

Ảnh Neo4j: `report/img/kg_count.png`, `report/img/kg_cross_kb.png`, `report/img/kg_my_case.png` (chép từ ảnh Neo4j đã chụp trong `docs/img/`).
Người đã chọn cho `kg_my_case.png`: Dương Minh Tuấn.

## Vấn đề gặp phải (không tính điểm)

Lỗi chưa giải quyết được: lệnh đã chạy, toàn bộ thông báo lỗi, những gì đã thử.
> `python bench_kg.py --check` chưa được chạy lại sau thay đổi vì lệnh reset graph trước khi build; graph và ảnh chụp Neo4j hiện có được giữ nguyên. Cần chạy tự kiểm sau khi sẵn sàng cho phép nạp lại graph.
