# 📚 Student Promotion System - Complete Guide

## How Student Promotion Works

---

## 🎯 Overview

The promotion system allows **Class Teachers** to promote students from one class to another at the end of the academic year. It tracks the complete history of student progression through school.

---

## 👥 Who Can Promote Students?

### ✅ **Class Teachers Only**
- Must be assigned as the **Class Teacher** for the source class
- Only they can promote students from their class

### ✅ **Super Admins**
- Can promote students from any class
- Full override privileges

### ❌ **Regular Teachers**
- Cannot promote students
- Can only view their assigned classes

---

## 📋 How It Works - Step by Step

### **Scenario: End of Academic Year 2024/2025**

**Setup:**
```
Current Situation:
- John Doe is in Class 5
- Academic Year: 2024/2025
- Third Term has ended
- John passed all subjects (75% average)
- Time to move him to Class 6 for 2025/2026
```

### **Step 1: Teacher Accesses Promotion Interface**

**Location:** Teacher Dashboard → Promote Students

**What Teacher Sees:**
```
┌──────────────────────────────────────────┐
│ PROMOTE STUDENTS                         │
├──────────────────────────────────────────┤
│                                          │
│ From Class:  [Class 5 ▼]                │
│                                          │
│ To Class:    [Class 6 ▼]                │
│                                          │
│ Academic Year: [2025/2026]               │
│                                          │
│ [Load Students]                          │
└──────────────────────────────────────────┘
```

### **Step 2: System Loads Eligible Students**

**API Call:**
```
GET /api/v1/teachers/class/5/promotion-eligible/
```

**Response:**
```json
{
  "success": true,
  "students": [
    {
      "id": 123,
      "student_id": "STU2024001",
      "name": "John Doe",
      "roll_number": "05",
      "average_score": 75.5,
      "attendance_rate": 92.3,
      "eligible": true,
      "recommendation": "Promote"
    },
    {
      "id": 124,
      "student_id": "STU2024002",
      "name": "Jane Smith",
      "average_score": 45.2,
      "attendance_rate": 78.5,
      "eligible": false,
      "recommendation": "Repeat"
    }
  ]
}
```

**What Teacher Sees:**
```
┌─────────────────────────────────────────────────────────────┐
│ STUDENTS IN CLASS 5 (2024/2025)                            │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│ ☑ John Doe (STU2024001)                                    │
│   Roll: 05 | Avg: 75.5% | Attendance: 92.3%                │
│   ✅ Recommendation: PROMOTE                                │
│                                                             │
│ ☐ Jane Smith (STU2024002)                                  │
│   Roll: 06 | Avg: 45.2% | Attendance: 78.5%                │
│   ⚠️  Recommendation: REPEAT/REVIEW                         │
│                                                             │
│ ☑ Peter Brown (STU2024003)                                 │
│   Roll: 07 | Avg: 82.1% | Attendance: 95.0%                │
│   ✅ Recommendation: PROMOTE                                │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│ [Select All] [Deselect All]                                │
│                                                             │
│ [Promote Selected Students]                                │
└─────────────────────────────────────────────────────────────┘
```

### **Step 3: Teacher Selects Students to Promote**

Teacher checks:
- ✅ John Doe
- ❌ Jane Smith (needs to repeat Class 5)
- ✅ Peter Brown

### **Step 4: Teacher Clicks "Promote Selected Students"**

**API Call:**
```
POST /api/v1/teachers/promote-students/

Request Body:
{
  "from_class_id": 5,
  "to_class_id": 6,
  "academic_year": "2025/2026",
  "student_ids": [123, 125]  // John and Peter
}
```

### **Step 5: System Processes Promotion**

**What Happens Behind the Scenes:**

#### **5.1: Creates Promotion Record**
```sql
INSERT INTO student_promotions (
  student_id,
  from_class_id,
  to_class_id,
  academic_year,
  promotion_type,
  promoted_by,
  promoted_at
) VALUES (
  123,                    -- John Doe
  5,                      -- From Class 5
  6,                      -- To Class 6
  '2025/2026',
  'promoted',
  1,                      -- Teacher's user ID
  NOW()
);
```

#### **5.2: Updates Student Record**
```sql
UPDATE students
SET
  current_class_id = 6,           -- Moved to Class 6
  academic_year = '2025/2026'     -- New academic year
WHERE id = 123;
```

#### **5.3: Creates Fee Records for New Class** (Automatic via signal)
```sql
-- System automatically creates StudentFee records
INSERT INTO student_fees (student_id, fee_structure_id, ...)
VALUES
  (123, <Class 6 - First Term>),
  (123, <Class 6 - Second Term>),
  (123, <Class 6 - Third Term>);
```

**Response:**
```json
{
  "success": true,
  "message": "Successfully promoted 2 student(s)",
  "promoted_count": 2,
  "from_class": "Class 5",
  "to_class": "Class 6",
  "errors": []
}
```

**What Teacher Sees:**
```
┌──────────────────────────────────────────┐
│ ✅ SUCCESS!                              │
├──────────────────────────────────────────┤
│                                          │
│ Successfully promoted 2 students         │
│ from Class 5 to Class 6                  │
│                                          │
│ Promoted Students:                       │
│ • John Doe (STU2024001)                  │
│ • Peter Brown (STU2024003)               │
│                                          │
│ [OK]                                     │
└──────────────────────────────────────────┘
```

---

## 📊 What Gets Updated When Students Are Promoted

### **1. Student Record**
```
BEFORE Promotion:
├── current_class: Class 5
├── academic_year: 2024/2025
└── status: active

AFTER Promotion:
├── current_class: Class 6 ✅ (Changed)
├── academic_year: 2025/2026 ✅ (Changed)
└── status: active
```

### **2. Promotion History (New Record Created)**
```
StudentPromotion Record:
├── student: John Doe (STU2024001)
├── from_class: Class 5
├── to_class: Class 6
├── academic_year: 2025/2026
├── promotion_type: promoted
├── promoted_by: Mr. Teacher
├── promoted_at: 2025-08-15 10:30:00
└── notes: (empty)
```

### **3. Fee Structures (Automatic)**
```
New StudentFee Records Created:
├── Class 6 - First Term 2025/2026: GHS 515 (Pending)
├── Class 6 - Second Term 2025/2026: GHS 515 (Pending)
└── Class 6 - Third Term 2025/2026: GHS 515 (Pending)

Old Fees (Remain Unchanged):
├── Class 5 - First Term 2024/2025: GHS 515 (Paid)
├── Class 5 - Second Term 2024/2025: GHS 515 (Paid)
└── Class 5 - Third Term 2024/2025: GHS 315 (Unpaid) ⚠️
```

### **4. Grades and Attendance (Preserved)**
```
All historical data is preserved:
├── Class 5 grades (2024/2025) ✅ Kept
├── Class 5 attendance (2024/2025) ✅ Kept
├── Class 5 assignments (2024/2025) ✅ Kept
└── All data remains accessible via history
```

---

## 🔄 Complete Promotion Workflow Diagram

```
START: End of Academic Year
│
├─ Class Teacher logs in
│  └─ Goes to "Promote Students" section
│
├─ Step 1: Select Source Class
│  └─ Teacher selects: Class 5
│
├─ Step 2: Select Target Class
│  └─ Teacher selects: Class 6
│
├─ Step 3: Enter Academic Year
│  └─ Teacher enters: 2025/2026
│
├─ Step 4: Load Students
│  ├─ System fetches all students in Class 5
│  ├─ Calculates average scores
│  ├─ Calculates attendance rates
│  └─ Shows recommendations
│
├─ Step 5: Teacher Reviews & Selects
│  ├─ Reviews each student's performance
│  ├─ Selects students to promote
│  └─ Leaves behind students to repeat
│
├─ Step 6: Teacher Clicks "Promote"
│  └─ API call sent to backend
│
├─ Step 7: System Validates
│  ├─ Checks teacher permissions ✅
│  ├─ Validates class exists ✅
│  ├─ Validates students exist ✅
│  └─ Checks students are in source class ✅
│
├─ Step 8: Database Transaction (Atomic)
│  ├─ For each selected student:
│  │  ├─ Create StudentPromotion record
│  │  ├─ Update student.current_class
│  │  ├─ Update student.academic_year
│  │  └─ Trigger fee creation (signal)
│  └─ Commit all changes at once
│
├─ Step 9: Response Sent
│  └─ Success message with count
│
└─ Step 10: Teacher Sees Confirmation
   └─ Students now appear in Class 6
```

---

## 🎓 Real-World Example: Full Promotion Cycle

### **School: Unique Success Academy**
### **Date: August 2025 (New Academic Year)**

### **Classes:**
- **Nursery 1** → Nursery 2
- **Nursery 2** → Kindergarten 1
- **Kindergarten 2** → Class 1
- **Class 1** → Class 2
- **Class 2** → Class 3
- **Class 5** → Class 6
- **JHS 2** → JHS 3

### **Promotion Process:**

#### **Week 1: Class Teachers Receive Instructions**
```
Email to all Class Teachers:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Subject: Student Promotion for 2025/2026

Dear Class Teachers,

Please promote eligible students from your class
to the next level for the 2025/2026 academic year.

Login to Teacher Dashboard → Promote Students

Deadline: August 20, 2025

Regards,
Admin
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

#### **Week 2: Class 5 Teacher Promotes Students**

**Class 5 Teacher: Mr. Johnson**

**Original Class 5 (2024/2025):**
```
Total Students: 25

Performance Breakdown:
├── Excellent (80%+): 12 students → Promote to Class 6
├── Good (60-79%): 8 students → Promote to Class 6
├── Average (50-59%): 3 students → Promote to Class 6
└── Below Average (<50%): 2 students → Repeat Class 5
```

**Promotion Action:**
```
From Class: Class 5
To Class: Class 6
Academic Year: 2025/2026
Selected Students: 23 (excluding 2 low performers)

[PROMOTE] clicked at 10:15 AM
```

**Result:**
```
✅ Successfully promoted 23 students
⚠️  2 students remain in Class 5 (to repeat)

Class 6 (2025/2026) now has:
├── 23 promoted from Class 5
└── Waiting for new admissions
```

#### **What Happens to Non-Promoted Students?**

**Jane Smith (Failed):**
```
BEFORE:
├── Class: Class 5
├── Academic Year: 2024/2025
├── Status: active

AFTER (Not promoted):
├── Class: Class 5 (Still here)
├── Academic Year: 2024/2025 (Teacher must manually update)
├── Status: active

Teacher Action Required:
└── Must manually update academic_year to 2025/2026
    so Jane repeats Class 5 in new academic year
```

---

## 🔐 Security & Permissions

### **Who Can Promote:**
```python
# Permission Check (from code)
is_class_teacher = TeacherClassAssignment.objects.filter(
    teacher=user,
    class_obj=from_class,
    is_class_teacher=True,  # Must be CLASS TEACHER
    is_active=True
).exists()

if not is_class_teacher and not user.is_superuser:
    return ERROR: "Only class teacher can promote"
```

### **Validation Checks:**
1. ✅ User must be authenticated
2. ✅ User must be teacher or super admin
3. ✅ User must be CLASS TEACHER of source class
4. ✅ Source and target classes must exist
5. ✅ Students must be in source class
6. ✅ Academic year must be provided

---

## 📈 Viewing Promotion History

### **For Administrators:**
```python
# Get all promotions for a student
from apps.admissions.models import StudentPromotion

student = Student.objects.get(student_id='STU2024001')
promotions = StudentPromotion.objects.filter(student=student).order_by('promoted_at')

for p in promotions:
    print(f"{p.academic_year}: {p.from_class.name} → {p.to_class.name} ({p.promotion_type})")
```

**Output:**
```
2020/2021: Nursery 1 → Nursery 2 (promoted)
2021/2022: Nursery 2 → Kindergarten 1 (promoted)
2022/2023: Kindergarten 1 → Kindergarten 2 (promoted)
2023/2024: Kindergarten 2 → Class 1 (promoted)
2024/2025: Class 1 → Class 2 (promoted)
2025/2026: Class 2 → Class 3 (promoted)
```

---

## 🚨 Common Issues & Solutions

### **Issue 1: "Only class teacher can promote students"**

**Problem:**
```
Teacher tries to promote but gets error:
"Only the class teacher can promote students from this class"
```

**Solution:**
```
Admin must assign teacher as CLASS TEACHER:

1. Go to Admin Panel
2. Navigate to Teacher Class Assignments
3. Find the teacher's assignment to that class
4. Check the box: ☑ Is Class Teacher
5. Save
```

### **Issue 2: Student appears in both classes**

**Problem:**
```
After promotion, student shows in both Class 5 and Class 6
```

**Cause:**
```
Old data cached or page not refreshed
```

**Solution:**
```
1. Refresh the page (Ctrl+F5)
2. Check database directly:
   SELECT current_class_id FROM students WHERE id = 123;
3. Verify promotion record was created:
   SELECT * FROM student_promotions WHERE student_id = 123;
```

### **Issue 3: Fees not created for new class**

**Problem:**
```
Student promoted but no fees showing for new class
```

**Solution:**
```bash
# Check if fee structures exist for new class
python3 manage.py shell -c "
from apps.finance.models import FeeStructure
from apps.academics.models import Class

class_obj = Class.objects.get(name='Class 6')
fee_structures = FeeStructure.objects.filter(
    class_level=class_obj,
    academic_year='2025/2026'
)
print(f'Fee structures: {fee_structures.count()}')
"

# If 0, create them:
python3 manage.py setup_fee_structures --academic-year="2025/2026"
```

---

## 📝 Best Practices

### ✅ **Do's:**
1. **Review performance before promoting**
   - Check average scores
   - Review attendance rates
   - Consider behavior/conduct

2. **Promote at end of academic year**
   - Do bulk promotions together
   - Ensure all grades are entered
   - Verify all fees are settled

3. **Document special cases**
   - Add notes for students who repeat
   - Record reasons for non-promotion
   - Keep communication with parents

4. **Double-check selections**
   - Review selected students before clicking promote
   - Verify target class is correct
   - Confirm academic year is accurate

### ❌ **Don'ts:**
1. **Don't promote mid-year**
   - Causes fee structure confusion
   - Disrupts grade tracking

2. **Don't promote without reviewing data**
   - Always check student performance first
   - Verify attendance records

3. **Don't skip struggling students by accident**
   - Some may need to repeat
   - Document decisions

---

## 🔍 API Endpoints

### **1. Get Eligible Students**
```
GET /api/v1/teachers/class/{class_id}/promotion-eligible/

Response:
{
  "success": true,
  "students": [...],
  "class_name": "Class 5",
  "total_students": 25
}
```

### **2. Promote Students**
```
POST /api/v1/teachers/promote-students/

Request:
{
  "from_class_id": 5,
  "to_class_id": 6,
  "academic_year": "2025/2026",
  "student_ids": [123, 124, 125]
}

Response:
{
  "success": true,
  "message": "Successfully promoted 3 student(s)",
  "promoted_count": 3,
  "from_class": "Class 5",
  "to_class": "Class 6"
}
```

---

## 📚 Database Schema

### **StudentPromotion Model:**
```python
class StudentPromotion(models.Model):
    student = ForeignKey(Student)              # Who was promoted
    from_class = ForeignKey(Class)             # Original class
    to_class = ForeignKey(Class)               # New class
    academic_year = CharField(max_length=20)   # When promoted (e.g., "2025/2026")
    promotion_type = CharField(choices=[       # Type of promotion
        ('promoted', 'Promoted'),
        ('repeated', 'Repeated')
    ])
    promoted_at = DateTimeField(auto_now_add=True)  # Timestamp
    promoted_by = ForeignKey(User)             # Who did the promotion
    notes = TextField(blank=True)              # Optional notes
```

---

**🎉 That's how the complete promotion system works!**
