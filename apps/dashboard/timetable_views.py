# apps/dashboard/timetable_views.py - COMPLETE FIXED VERSION
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.db import transaction
from apps.academics.models import (
    Class, Subject, Timetable, TimetableEntry,
    TimeSlot, ClassSubject, TeacherClassAssignment
)
from apps.accounts.models import User


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_time_slots(request):
    """Get all available time slots"""
    if request.user.role not in ['admin', 'super_admin'] and not request.user.is_superuser:
        return Response({'success': False, 'error': 'Admin access required'},
                       status=status.HTTP_403_FORBIDDEN)

    time_slots = TimeSlot.objects.filter(is_active=True).order_by('start_time')

    slots_data = []
    for slot in time_slots:
        slots_data.append({
            'id': slot.id,
            'name': slot.name,
            'start_time': slot.start_time.strftime('%H:%M'),
            'end_time': slot.end_time.strftime('%H:%M'),
            'is_break': slot.is_break,
            'day_of_week': slot.day_of_week if hasattr(slot, 'day_of_week') else None
        })

    return Response({
        'success': True,
        'data': slots_data
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_time_slot(request):
    """Create a new time slot"""
    if request.user.role not in ['admin', 'super_admin'] and not request.user.is_superuser:
        return Response({'success': False, 'error': 'Admin access required'},
                       status=status.HTTP_403_FORBIDDEN)

    name = request.data.get('name')
    start_time = request.data.get('start_time')
    end_time = request.data.get('end_time')
    is_break = request.data.get('is_break', False)

    if not all([name, start_time, end_time]):
        return Response({'success': False, 'error': 'Missing required fields'},
                       status=status.HTTP_400_BAD_REQUEST)

    try:
        time_slot = TimeSlot.objects.create(
            name=name,
            start_time=start_time,
            end_time=end_time,
            is_break=is_break,
            is_active=True
        )

        return Response({
            'success': True,
            'message': 'Time slot created successfully',
            'data': {
                'id': time_slot.id,
                'name': time_slot.name
            }
        }, status=status.HTTP_201_CREATED)

    except Exception as e:
        return Response({'success': False, 'error': str(e)},
                       status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_class_timetable(request, class_id):
    """Get timetable for a specific class"""
    if request.user.role not in ['admin', 'super_admin', 'teacher'] and not request.user.is_superuser:
        return Response({'success': False, 'error': 'Access denied'},
                       status=status.HTTP_403_FORBIDDEN)

    try:
        class_obj = Class.objects.get(id=class_id)

        # Get active timetable
        timetable = Timetable.objects.filter(
            class_obj=class_obj,
            is_active=True
        ).first()

        if not timetable:
            return Response({
                'success': True,
                'data': {
                    'timetable_exists': False,
                    'class_name': class_obj.name,
                    'entries': []
                }
            })

        # Get all entries
        entries = TimetableEntry.objects.filter(
            timetable=timetable
        ).select_related('subject', 'teacher', 'time_slot').order_by(
            'day_of_week', 'time_slot__start_time'
        )

        entries_data = []
        for entry in entries:
            entry_dict = {
                'id': entry.id,
                'day_of_week': entry.day_of_week,
                'time_slot_id': entry.time_slot.id,
                'time_slot_name': entry.time_slot.name,
                'time_slot': entry.time_slot.name,  # Add this for frontend compatibility
                'start_time': entry.time_slot.start_time.strftime('%H:%M'),
                'end_time': entry.time_slot.end_time.strftime('%H:%M'),
                'subject_id': entry.subject.id if entry.subject else None,
                'subject_name': entry.subject.name if entry.subject else 'Break',
                'subject': entry.subject.name if entry.subject else 'Break',  # Add this
                'teacher_id': entry.teacher.id if entry.teacher else None,
                'teacher_name': entry.teacher.get_full_name() if entry.teacher else 'TBA',
                'teacher': entry.teacher.get_full_name() if entry.teacher else 'TBA',  # Add this
                'room_number': entry.room_number or '',
                'room': entry.room_number or '-'  # Add this for frontend
            }
            entries_data.append(entry_dict)
            
        print(f"📊 Returning {len(entries_data)} entries for class {class_obj.name}")
        print(f"📊 Sample entry: {entries_data[0] if entries_data else 'No entries'}")

        return Response({
            'success': True,
            'data': {
                'timetable_exists': True,
                'timetable_id': timetable.id,
                'class_name': class_obj.name,
                'academic_year': timetable.academic_year,
                'term': timetable.term,
                'entries': entries_data
            }
        })

    except Class.DoesNotExist:
        return Response({'success': False, 'error': 'Class not found'},
                       status=status.HTTP_404_NOT_FOUND)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_timetable(request):
    """Create a new timetable for a class"""
    if request.user.role not in ['admin', 'super_admin'] and not request.user.is_superuser:
        return Response({'success': False, 'error': 'Admin access required'},
                       status=status.HTTP_403_FORBIDDEN)

    class_id = request.data.get('class_id')
    academic_year = request.data.get('academic_year', '2024-2025')
    term = request.data.get('term', 'first')

    if not class_id:
        return Response({'success': False, 'error': 'Class ID required'},
                       status=status.HTTP_400_BAD_REQUEST)

    try:
        class_obj = Class.objects.get(id=class_id)

        # Deactivate existing timetables
        Timetable.objects.filter(class_obj=class_obj).update(is_active=False)

        # Create new timetable
        timetable = Timetable.objects.create(
            class_obj=class_obj,
            academic_year=academic_year,
            term=term,
            is_active=True
        )

        return Response({
            'success': True,
            'message': 'Timetable created successfully',
            'data': {
                'timetable_id': timetable.id,
                'class_id': class_obj.id,
                'class_name': class_obj.name
            }
        }, status=status.HTTP_201_CREATED)

    except Class.DoesNotExist:
        return Response({'success': False, 'error': 'Class not found'},
                       status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({'success': False, 'error': str(e)},
                       status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_or_update_timetable_entry(request):
    """Create or update a timetable entry"""
    if request.user.role not in ['admin', 'super_admin'] and not request.user.is_superuser:
        return Response({'success': False, 'error': 'Admin access required'},
                       status=status.HTTP_403_FORBIDDEN)

    entry_id = request.data.get('id')
    timetable_id = request.data.get('timetable_id')
    class_id = request.data.get('class_id')
    time_slot_input = request.data.get('time_slot')
    day_of_week = request.data.get('day_of_week')
    subject_id = request.data.get('subject_id')
    teacher_id = request.data.get('teacher_id')
    room_number = request.data.get('room_number', '')

    # Debug logging
    print(f"🔍 Received data: id={entry_id}, time_slot={time_slot_input}, day={day_of_week}, subject={subject_id}, teacher={teacher_id}")
    print(f"🔍 Request user: {request.user}, role: {request.user.role}")

    if not all([time_slot_input, day_of_week]):
        return Response({'success': False, 'error': 'Missing required fields: time_slot and day_of_week'},
                       status=status.HTTP_400_BAD_REQUEST)

    try:
        with transaction.atomic():
            # Get or create timetable
            if timetable_id:
                timetable = Timetable.objects.get(id=timetable_id)
            elif class_id:
                class_obj = Class.objects.get(id=class_id)
                timetable = Timetable.objects.filter(
                    class_obj=class_obj,
                    is_active=True
                ).first()

                if not timetable:
                    timetable = Timetable.objects.create(
                        class_obj=class_obj,
                        academic_year='2024-2025',
                        term='first',
                        is_active=True
                    )
            else:
                return Response({'success': False, 'error': 'Timetable or Class ID required'},
                               status=status.HTTP_400_BAD_REQUEST)

            # Handle time_slot
            time_slot = None
            time_slot_str = str(time_slot_input).strip()
            
            if time_slot_str.isdigit():
                time_slot = TimeSlot.objects.get(id=int(time_slot_str))
            else:
                time_slot = TimeSlot.objects.filter(name=time_slot_str).first()
                
                if not time_slot:
                    try:
                        time_slot_str = time_slot_str.replace(' ', '')
                        
                        if '-' not in time_slot_str:
                            raise ValueError("No dash separator found")
                        
                        parts = time_slot_str.split('-')
                        if len(parts) != 2:
                            raise ValueError("Invalid format")
                        
                        start_time = parts[0].strip()
                        end_time = parts[1].strip()
                        
                        from datetime import datetime
                        start_dt = datetime.strptime(start_time, '%H:%M')
                        end_dt = datetime.strptime(end_time, '%H:%M')
                        
                        slot_order = start_dt.hour * 60 + start_dt.minute
                        readable_name = f"{start_time} - {end_time}"
                        
                        time_slot = TimeSlot.objects.create(
                            name=readable_name,
                            start_time=start_time,
                            end_time=end_time,
                            slot_order=slot_order,
                            slot_type='class',
                            is_active=True
                        )
                        print(f"✅ Created new TimeSlot: {time_slot.name} (order: {slot_order})")
                        
                    except (IndexError, ValueError) as e:
                        error_msg = f'Invalid time slot format: "{time_slot_input}". Expected "HH:MM - HH:MM" or "HH:MM-HH:MM"'
                        print(f"❌ {error_msg}")
                        return Response({'success': False, 'error': error_msg}, 
                                      status=status.HTTP_400_BAD_REQUEST)
            
            # Get related objects
            subject = None
            teacher = None
            
            if subject_id:
                try:
                    subject = Subject.objects.get(id=subject_id)
                except Subject.DoesNotExist:
                    return Response({'success': False, 'error': f'Subject with ID {subject_id} not found'}, 
                                  status=status.HTTP_404_NOT_FOUND)
            
            if teacher_id:
                try:
                    teacher = User.objects.get(id=teacher_id, role='teacher')
                except User.DoesNotExist:
                    return Response({'success': False, 'error': f'Teacher with ID {teacher_id} not found'}, 
                                  status=status.HTTP_404_NOT_FOUND)
            
            # Create or update entry
            if entry_id:
                try:
                    entry = TimetableEntry.objects.get(id=entry_id)
                    entry.time_slot = time_slot
                    entry.day_of_week = day_of_week
                    entry.subject = subject
                    entry.teacher = teacher
                    entry.room_number = room_number
                    entry.save()
                    message = 'Timetable entry updated successfully'
                    print(f"✅ Updated entry ID: {entry.id}")
                except TimetableEntry.DoesNotExist:
                    return Response({'success': False, 'error': f'Entry with ID {entry_id} not found'}, 
                                  status=status.HTTP_404_NOT_FOUND)
            else:
                existing = TimetableEntry.objects.filter(
                    timetable=timetable,
                    time_slot=time_slot,
                    day_of_week=day_of_week
                ).first()
                
                if existing:
                    existing.subject = subject
                    existing.teacher = teacher
                    existing.room_number = room_number
                    existing.save()
                    entry = existing
                    message = 'Timetable entry updated (slot already existed)'
                    print(f"✅ Updated existing entry ID: {entry.id}")
                else:
                    entry = TimetableEntry.objects.create(
                        timetable=timetable,
                        time_slot=time_slot,
                        day_of_week=day_of_week,
                        subject=subject,
                        teacher=teacher,
                        room_number=room_number
                    )
                    message = 'Timetable entry created successfully'
                    print(f"✅ Created new entry ID: {entry.id}")
            
            return Response({
                'success': True,
                'message': message,
                'data': {
                    'entry_id': entry.id,
                    'timetable_id': timetable.id,
                    'time_slot_id': time_slot.id,
                    'time_slot_name': time_slot.name
                }
            }, status=status.HTTP_201_CREATED if not entry_id else status.HTTP_200_OK)
            
    except Class.DoesNotExist:
        return Response({'success': False, 'error': f'Class with ID {class_id} not found'}, 
                       status=status.HTTP_404_NOT_FOUND)
    except Timetable.DoesNotExist:
        return Response({'success': False, 'error': f'Timetable with ID {timetable_id} not found'}, 
                       status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        import traceback
        print(f"❌ Server error: {str(e)}")
        print(traceback.format_exc())
        return Response({'success': False, 'error': f'Server error: {str(e)}'}, 
                       status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_timetable_entry(request, entry_id):
    """Delete a timetable entry - FIXED URL HANDLING"""
    if request.user.role not in ['admin', 'super_admin'] and not request.user.is_superuser:
        return Response({'success': False, 'error': 'Admin access required'}, 
                       status=status.HTTP_403_FORBIDDEN)
    
    print(f"🗑️ Attempting to delete entry ID: {entry_id}")
    
    try:
        entry = TimetableEntry.objects.get(id=entry_id)
        entry_info = f"{entry.day_of_week} - {entry.time_slot.name}"
        entry.delete()
        
        print(f"✅ Successfully deleted entry: {entry_info}")
        
        return Response({
            'success': True,
            'message': 'Timetable entry deleted successfully'
        })
        
    except TimetableEntry.DoesNotExist:
        print(f"❌ Entry ID {entry_id} not found")
        return Response({'success': False, 'error': 'Entry not found'}, 
                       status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        print(f"❌ Error deleting entry: {str(e)}")
        return Response({'success': False, 'error': str(e)}, 
                       status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_subjects_and_teachers(request, class_id):
    """Get available subjects and teachers for a class"""
    if request.user.role not in ['admin', 'super_admin'] and not request.user.is_superuser:
        return Response({'success': False, 'error': 'Admin access required'}, 
                       status=status.HTTP_403_FORBIDDEN)
    
    try:
        class_obj = Class.objects.get(id=class_id)
        
        # Get subjects assigned to this class
        class_subjects = ClassSubject.objects.filter(
            class_obj=class_obj,
            is_active=True
        ).select_related('subject', 'teacher')
        
        subjects_data = []
        for cs in class_subjects:
            subjects_data.append({
                'id': cs.subject.id,
                'name': cs.subject.name,
                'code': cs.subject.code,
                'default_teacher_id': cs.teacher.id if cs.teacher else None,
                'default_teacher_name': cs.teacher.get_full_name() if cs.teacher else None
            })
        
        # Get all teachers
        teachers = User.objects.filter(role='teacher', is_active=True)
        teachers_data = []
        for teacher in teachers:
            teachers_data.append({
                'id': teacher.id,
                'name': teacher.get_full_name(),
                'email': teacher.email
            })
        
        return Response({
            'success': True,
            'data': {
                'subjects': subjects_data,
                'teachers': teachers_data
            }
        })
        
    except Class.DoesNotExist:
        return Response({'success': False, 'error': 'Class not found'}, 
                       status=status.HTTP_404_NOT_FOUND)


