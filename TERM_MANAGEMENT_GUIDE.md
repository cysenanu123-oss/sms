# 📚 Term Management Guide

## How to Set Term Duration and Switch Terms

---

## 🎯 Method 1: Manual Term Switching (via Admin Dashboard)

### **Step-by-Step:**

1. **Login as Admin**
   - Go to: `http://your-domain.com/admin-dashboard`

2. **Navigate to Settings**
   - Click **Settings** in the left sidebar

3. **Find Academic Settings Section**
   - You'll see a card titled "Academic Settings"
   - Current term status is displayed at the top

4. **Update Term Information:**
   ```
   Current Academic Year: 2024/2025
   Current Term: [Select from dropdown]
      - First Term
      - Second Term
      - Third Term
   Term Start Date: [Pick date]
   Term End Date: [Pick date]
   ```

5. **Click "Save Changes"**
   - System will show confirmation
   - All dashboards immediately switch to new term

### **Example: Switching from First Term to Second Term**

```
Before:
✅ Current Term: First Term (2024/2025)
   Sept 1, 2024 - Dec 15, 2024

After Update:
Current Academic Year: 2024/2025
Current Term: Second Term
Term Start Date: 2025-01-06
Term End Date: 2025-04-15

[Click Save Changes]

Result:
✅ Current Term: Second Term (2024/2025)
   Jan 6, 2025 - Apr 15, 2025
```

---

## 🤖 Method 2: Automatic Term Switching

The system can automatically switch terms based on dates!

### **How It Works:**

1. **System checks current date daily**
2. **If date > term_end_date:**
   - Automatically switches to next term
   - Updates dates automatically
   - Creates fee structures for new term
   - Logs the change

### **Setup Automatic Switching:**

#### **Option A: Run Daily via Cron Job (Recommended for Production)**

1. Open crontab editor:
   ```bash
   crontab -e
   ```

2. Add this line (runs every day at 1 AM):
   ```bash
   0 1 * * * cd /home/cyril/sms && python3 manage.py check_term_switch >> /var/log/term_switch.log 2>&1
   ```

3. Save and exit

#### **Option B: Test Manually**

Run this command to check if term should switch:
```bash
python3 manage.py check_term_switch
```

**Output Example:**
```
⏳ Current term: First Term (2024/2025)
   Days remaining: 14
```

Or if term needs switching:
```
✅ Term switched successfully!
   Old: First Term (2024/2025)
   New: Second Term (2024/2025)
   Start: 2025-01-06
   End: 2025-04-15
✅ Created 10 fee structures for new term
```

---

## 💰 Automatic Fee Structure Creation

When a new term starts (automatically or manually), the system:

### **What Happens:**

1. **Checks if fee structures exist for new term**
2. **If not, copies from previous term:**
   - Tuition Fee ✅
   - Examination Fee ✅
   - Library Fee ✅
   - Sports Fee ✅
   - Lab Fee ✅
   - Transport Fee ✅
   - Other Fees ✅
3. **Sets admission_fee = 0** (only for new students)
4. **Sets due_date = term_end_date**

### **Fee Structure Logic:**

```
Previous Term: First Term 2024/2025
- Class 1A: GHS 500 tuition
- Class 2A: GHS 600 tuition
- Class 3A: GHS 700 tuition

New Term: Second Term 2024/2025
→ System automatically creates:
- Class 1A: GHS 500 tuition (copied)
- Class 2A: GHS 600 tuition (copied)
- Class 3A: GHS 700 tuition (copied)
```

---

## 📅 Typical Ghana School Calendar

### **Term Structure:**

| Term | Start Date | End Date | Weeks |
|------|------------|----------|-------|
| **First Term** | September 1 | December 15 | ~14 weeks |
| **Second Term** | January 6 | April 15 | ~14 weeks |
| **Third Term** | May 1 | July 31 | ~12 weeks |

### **When Term Ends:**

**Scenario:** Today is December 16, 2024 (First Term has ended)

**If automatic switching is enabled:**
```bash
# System runs at 1 AM on Dec 16
python3 manage.py check_term_switch

Result:
✅ Term switched successfully!
   Old: First Term (2024/2025)
   New: Second Term (2024/2025)
   Start: 2025-01-06
   End: 2025-04-15
✅ Created 15 fee structures for new term
```

**If automatic switching is NOT enabled:**
- Admin must manually update via Settings page
- Fee structures must be created manually (or run command)

---

## 🎓 End of Academic Year (Third Term → First Term)

### **What Happens:**

When Third Term ends and switches to First Term:

1. **Academic year updates automatically:**
   ```
   Old: 2024/2025 - Third Term
   New: 2025/2026 - First Term
   ```

2. **Students need to be promoted:**
   - Go to Admin Dashboard → Students
   - Select students from Class 1A
   - Promote to Class 2A
   - System tracks promotion history

3. **Fee structures created for new academic year**

4. **New classes can be created if needed**

---

## ⚙️ Manual Commands Reference

### **Check Term Status:**
```bash
python3 manage.py check_term_switch
```

### **Initialize School Settings (First Time):**
```bash
python3 manage.py init_school_settings
```

### **View Current Settings:**
```bash
python3 manage.py shell
>>> from apps.academics.models import SchoolSettings
>>> s = SchoolSettings.objects.first()
>>> print(f"Term: {s.get_current_term_display()}")
>>> print(f"Year: {s.current_academic_year}")
>>> print(f"Dates: {s.term_start_date} to {s.term_end_date}")
```

---

## 🚨 Important Notes

### **Manual vs Automatic:**

| Feature | Manual | Automatic (Cron) |
|---------|--------|------------------|
| **Term Switching** | Admin clicks Save | Happens at 1 AM daily |
| **Fee Creation** | Admin creates manually | Automatic (copies previous) |
| **Flexibility** | Change anytime | Based on dates only |
| **Control** | Full admin control | System handles it |

### **Best Practice:**

✅ **Use BOTH methods:**
- Set up automatic switching as backup
- Admin can manually override anytime via Settings page
- System ensures terms never get stuck

### **Safety Features:**

1. **Historical Data Protected:**
   - Old term data is never deleted
   - Students can view past terms via history
   - All grades, attendance, and fees preserved

2. **No Duplicate Fee Structures:**
   - System checks if fee structure already exists
   - Won't create duplicates

3. **Admin Override:**
   - Admin can manually change term anytime
   - Overrides automatic system

---

## 📊 Monitoring & Logs

### **Check if automatic switching is working:**

```bash
# View last 10 term switches
tail -n 10 /var/log/term_switch.log
```

### **Sample Log Output:**
```
[2024-12-16 01:00:00] ✅ Term switched successfully!
[2024-12-16 01:00:00]    Old: First Term (2024/2025)
[2024-12-16 01:00:00]    New: Second Term (2024/2025)
[2024-12-16 01:00:01] ✅ Created 15 fee structures for new term
```

---

## ❓ FAQ

### **Q: Can I change term dates mid-term?**
✅ Yes! Just update dates in Settings and click Save.

### **Q: What if I want to skip automatic switching for a specific date?**
✅ Just manually update the term_end_date to extend the current term.

### **Q: Do students lose their data when terms switch?**
❌ No! All data is preserved. They can view past terms via history.

### **Q: Can I switch back to a previous term?**
✅ Yes! Just select the previous term in Settings dropdown.

### **Q: How do I adjust fee amounts for new term?**
Go to Admin Dashboard → Finance → Fee Structures → Edit the amounts for the new term.

---

## 🎯 Quick Reference

**To manually switch terms:**
1. Admin Dashboard → Settings
2. Change "Current Term" dropdown
3. Update start/end dates
4. Click "Save Changes"

**To enable automatic switching:**
```bash
crontab -e
# Add: 0 1 * * * cd /home/cyril/sms && python3 manage.py check_term_switch
```

**To test automatic switching:**
```bash
python3 manage.py check_term_switch
```

---

**Need Help?** Check `/var/log/term_switch.log` or contact system administrator.
