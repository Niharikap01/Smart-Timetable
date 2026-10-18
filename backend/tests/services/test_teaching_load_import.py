from app.services.teaching_load_import import parse_explicit_allocations


def test_reads_clear_faculty_to_section_assignment():
    assignments, issues = parse_explicit_allocations("Faculty_068 (2) [A2, A7]")

    assert assignments == [("FACULTY_068", ["A2", "A7"])]
    assert issues == []


def test_preserves_ambiguous_theory_ta_mapping_for_review():
    assignments, issues = parse_explicit_allocations("Faculty_087 (2) Faculty_080(TA) [A1, A4]")

    assert assignments == []
    assert issues == ["ambiguous faculty-to-section mapping"]


def test_preserves_batch_only_assignment_for_review():
    assignments, issues = parse_explicit_allocations("Faculty_182 (4 Batches)")

    assert assignments == []
    assert issues == ["no explicit section list"]
