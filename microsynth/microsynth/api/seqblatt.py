import frappe

@frappe.whitelist()
def get_unused_easy_run_label_ranges():
    """
    Return ranges of all unused Sequencing Labels for Item Code 3050 where label_id needs to be grouped into barcode_start_range to barcode_start_range.
    Return example:
    {
        "message": {
            "success": true,
            "message": "OK",
            "internal_message": null,
            "ranges": [
                {
                    "contact": "215856",
                    "registered": false,
                    "registered_to": null,
                    "item": "3050",
                    "barcode_start_range": "642601",
                    "barcode_end_range": "642700",
                    "sales_order": "SO-GOE-26007741",
                    "web_order_id": 4722438
                },
                {
                    "contact": "215856",
                    "registered": true,
                    "registered_to": "237365",
                    "item": "3050",
                    "barcode_start_range": "642801",
                    "barcode_end_range": "642900",
                    "sales_order": "SO-GOE-26007741",
                    "web_order_id": 4722438
                }
            ]
        }
    }

    bench execute microsynth.microsynth.api.seqblatt.get_unused_easy_run_label_ranges
    """
    sql_query = """
        SELECT
            `sequencing_label_grouped`.`contact`,
            `sequencing_label_grouped`.`registered`,
            `sequencing_label_grouped`.`registered_to`,
            `sequencing_label_grouped`.`item`,
            `sequencing_label_grouped`.`sales_order`,
            (SELECT `web_order_id` FROM `tabSales Order` WHERE `name` = `sequencing_label_grouped`.`sales_order`) AS `web_order_id`,
            MIN(`sequencing_label_grouped`.`label_id`) AS `barcode_start_range`,
            MAX(`sequencing_label_grouped`.`label_id`) AS `barcode_end_range`
        FROM (
            SELECT
                `tabSequencing Label`.`contact`,
                `tabSequencing Label`.`registered`,
                `tabSequencing Label`.`registered_to`,
                `tabSequencing Label`.`item`,
                `tabSequencing Label`.`sales_order`,
                `tabSequencing Label`.`label_id`,
                `tabSequencing Label`.`label_id` - ROW_NUMBER() OVER (
                    PARTITION BY
                        `tabSequencing Label`.`contact`,
                        `tabSequencing Label`.`registered`,
                        `tabSequencing Label`.`registered_to`,
                        `tabSequencing Label`.`item`
                    ORDER BY
                        `tabSequencing Label`.`label_id`
                ) AS `group_identifier`
            FROM `tabSequencing Label`
            WHERE
                `tabSequencing Label`.`item` = '3050'
                AND `tabSequencing Label`.`status` = 'unused'
        ) AS `sequencing_label_grouped`
        GROUP BY
            `sequencing_label_grouped`.`contact`,
            `sequencing_label_grouped`.`registered`,
            `sequencing_label_grouped`.`registered_to`,
            `sequencing_label_grouped`.`item`,
            `sequencing_label_grouped`.`sales_order`,
            `sequencing_label_grouped`.`group_identifier`
        ORDER BY
            `barcode_start_range`
        """
    ranges = frappe.db.sql(sql_query, as_dict=True)
    return {
        "success": True,
        "message": "OK",
        "internal_message": None,
        "ranges": ranges
    }


### The following functions are alternative implementations of the same logic as get_unused_easy_run_label_ranges but implemented in Python without SQL window functions.

# def get_unused_easy_run_label_ranges_simple():
#     """
#     Same as get_unused_easy_run_label_ranges but implemented in Python without SQL window functions.
#     Should return the same result but is expected to be much slower. Used for testing and comparison.

#     bench execute microsynth.microsynth.seqblatt.get_unused_easy_run_label_ranges_simple
#     """
#     rows = frappe.db.sql("""
#         SELECT
#             `contact`,
#             `registered`,
#             `registered_to`,
#             `item`,
#             `label_id`
#         FROM `tabSequencing Label`
#         WHERE
#             `item` = '3050'
#             AND `status` = 'unused'
#         ORDER BY
#             `contact`,
#             `registered`,
#             `registered_to`,
#             `item`,
#             `label_id`
#     """, as_dict=True)

#     # normalize types (important!)
#     for row in rows:
#         row["label_id"] = int(row["label_id"])
#         row["registered"] = int(row["registered"]) if row["registered"] is not None else 0
#         row["registered_to"] = row["registered_to"] or None

#     ranges = []
#     current = None

#     for row in rows:
#         key = (
#             row["contact"],
#             row["registered"],
#             row["registered_to"],
#             row["item"]
#         )
#         if current is None:
#             current = {"key": key, "start": row["label_id"], "end": row["label_id"]}
#             continue

#         # same group + consecutive?
#         if key == current["key"] and row["label_id"] == current["end"] + 1:
#             current["end"] = row["label_id"]
#         else:
#             ranges.append({
#                 "contact": current["key"][0],
#                 "registered": current["key"][1],
#                 "registered_to": current["key"][2],
#                 "item": current["key"][3],
#                 "barcode_start_range": current["start"],
#                 "barcode_end_range": current["end"]
#             })
#             current = {"key": key, "start": row["label_id"], "end": row["label_id"]}

#     # append last range
#     if current:
#         ranges.append({
#             "contact": current["key"][0],
#             "registered": current["key"][1],
#             "registered_to": current["key"][2],
#             "item": current["key"][3],
#             "barcode_start_range": current["start"],
#             "barcode_end_range": current["end"]
#         })

#     return {
#         "success": True,
#         "message": "OK",
#         "internal_message": None,
#         "ranges": ranges
#     }


# def compare_easy_run_label_range_methods(validate=True):
#     """
#     Compare SQL vs Python implementation for label range grouping.

#     bench execute microsynth.microsynth.seqblatt.compare_easy_run_label_range_methods --kwargs "{'validate': True}"
#     """
#     # 1. SQL (window function)
#     start_sql = time.perf_counter()
#     sql_result = get_unused_easy_run_label_ranges()
#     duration_sql = time.perf_counter() - start_sql
#     print(f"Efficient SQL: {duration_sql:.6f} seconds")

#     # 2. Python (simple)
#     start_py = time.perf_counter()
#     py_result = get_unused_easy_run_label_ranges_simple()
#     duration_py = time.perf_counter() - start_py
#     print(f"Efficient Python: {duration_py:.6f} seconds")

#     # 3. Python (very simple)
#     start_py_very_simple = time.perf_counter()
#     duration_py_very_simple = time.perf_counter() - start_py_very_simple
#     print(f"Non-efficient Python: {duration_py_very_simple:.6f} seconds")

#     # 4. Validation
#     start_validation = time.perf_counter()
#     is_equal_sql_py = None

#     if validate:
#         def normalize(ranges):
#             def s(val):
#                 return val or ""

#             return sorted([
#                 (
#                     s(r["contact"]),
#                     int(r["registered"]) if r["registered"] is not None else 0,
#                     s(r["registered_to"]),
#                     s(r["item"]),
#                     int(r["barcode_start_range"]),
#                     int(r["barcode_end_range"]),
#                 )
#                 for r in ranges
#             ])

#         sql_norm = normalize(sql_result["ranges"])
#         py_norm = normalize(py_result["ranges"])
#         is_equal_sql_py = sql_norm == py_norm

#         if not is_equal_sql_py:
#             print("[COMPARE] ❌ Mismatch detected!")
#             print("SQL (first 5):", sql_norm[:5])
#             print("PY efficient (first 5):", py_norm[:5])

#     duration_validation = time.perf_counter() - start_validation
#     print(f"Validation: {duration_validation:.6f} seconds")
#     print(f"Results identical SQL vs Efficient Python: {is_equal_sql_py}")
