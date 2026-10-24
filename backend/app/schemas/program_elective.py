from pydantic import BaseModel, Field, model_validator


class ProgramElectiveGroupCreate(BaseModel):
    group_name: str = Field(min_length=1, max_length=100)
    teacher_id: int = Field(gt=0)
    student_count: int = Field(gt=0, le=1000)
    section_ids: list[int] = Field(min_length=1)


class ProgramElectiveCreate(BaseModel):
    semester: int = Field(ge=1, le=12)
    course_code: str = Field(min_length=1, max_length=50)
    course_name: str = Field(min_length=1, max_length=200)
    periods_per_week: int = Field(gt=0, le=30)
    groups: list[ProgramElectiveGroupCreate] = Field(min_length=1, max_length=30)

    @model_validator(mode="after")
    def sections_appear_in_only_one_group(self):
        if not self.course_code.strip() or not self.course_name.strip():
            raise ValueError("Course code and name cannot be blank")
        section_ids = [section_id for group in self.groups for section_id in group.section_ids]
        if len(section_ids) != len(set(section_ids)):
            raise ValueError("A section can belong to only one group for this program elective")
        group_names = [group.group_name.strip().casefold() for group in self.groups]
        if any(not group_name for group_name in group_names):
            raise ValueError("Program-elective group names cannot be blank")
        if len(group_names) != len(set(group_names)):
            raise ValueError("Group names must be unique within a program elective")
        return self
