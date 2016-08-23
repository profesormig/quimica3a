from django.conf import settings
from django.db import models
from django.utils import timezone
from threepio import logger
from pprint import pprint

class AllocationSource(models.Model):
    name = models.CharField(max_length=255)
    source_id = models.CharField(max_length=255)
    compute_allowed = models.IntegerField()

    @classmethod
    def for_user(cls, user):
        source_ids = UserAllocationSource.objects.filter(user=user).values_list('allocation_source', flat=True)
        return AllocationSource.objects.filter(id__in=source_ids)

    def __unicode__(self):
        return "%s (ID:%s, Compute Allowed:%s)" %\
            (self.name, self.source_id,
             self.compute_allowed)


    class Meta:
        db_table = 'allocation_source'
        app_label = 'core'

class UserAllocationSource(models.Model):
    """
    This table keeps track of whih allocation sources belong to an AtmosphereUser.

    NOTE: This table is basically a cache so that we do not have to query out to the
    "Allocation Source X" API endpoint each call.
          It is presumed that this table will be *MAINTAINED* regularly via periodic task.
    """

    user = models.ForeignKey("AtmosphereUser")
    allocation_source = models.ForeignKey(AllocationSource, related_name="users")

    def __unicode__(self):
        return "%s (User:%s, AllocationSource:%s)" %\
            (self.id, self.user,
             self.allocation_source)

    class Meta:
        db_table = 'user_allocation_source'
        app_label = 'core'


class UserAllocationSnapshot(models.Model):
    """
    Fixme: Potential optimization -- user_allocation_source could just store burn_rate and updated?
    """
    user = models.ForeignKey("AtmosphereUser", related_name="user_allocation_snapshots")
    allocation_source = models.ForeignKey(AllocationSource, related_name="user_allocation_snapshots")
    # all fields are stored in DecimalField to allow for partial hour calculation
    compute_used = models.DecimalField(max_digits=19, decimal_places=3)
    burn_rate = models.DecimalField(max_digits=19, decimal_places=3)
    updated = models.DateTimeField(auto_now=True)

    def __unicode__(self):
        return "User %s + AllocationSource %s: Total AU Usage:%s Burn Rate:%s hours/hour Updated:%s" %\
            (self.user, self.allocation_source, self.compute_used, self.burn_rate, self.updated)

    class Meta:
        db_table = 'user_allocation_snapshot'
        app_label = 'core'
        unique_together = ('user','allocation_source')


class InstanceAllocationSourceSnapshot(models.Model):
    instance = models.OneToOneField("Instance")
    allocation_source = models.ForeignKey(AllocationSource)
    updated = models.DateTimeField(auto_now=True)

    def __unicode__(self):
        return "%s is using allocation %s" %\
            (self.instance, self.allocation_source)
    class Meta:
        db_table = 'instance_allocation_source_snapshot'
        app_label = 'core'


class AllocationSourceSnapshot(models.Model):
    allocation_source = models.OneToOneField(AllocationSource, related_name="snapshot")
    updated = models.DateTimeField(auto_now=True)
    # all fields are stored in DecimalField to allow for partial hour calculation
    global_burn_rate = models.DecimalField(max_digits=19, decimal_places=3)
    compute_used = models.DecimalField(max_digits=19, decimal_places=3)

    def __unicode__(self):
        return "%s (Used:%s, Burn Rate:%s Updated on:%s)" %\
            (self.allocation_source, self.compute_used,
             self.global_burn_rate, self.updated)
    class Meta:
        db_table = 'allocation_source_snapshot'
        app_label = 'core'

def total_usage(username, start_date, allocation_source_name=None,end_date=None, burn_rate=False):
    """ 
        This function outputs the total allocation usage in hours
    """
    from service.allocation_logic import create_report
    if not end_date:
        end_date = timezone.now()
    logger.info("Calculating total usage for User %s with AllocationSource %s from %s-%s" % (username, allocation_source_name, start_date, end_date))
    user_allocation = create_report(start_date,end_date,user_id=username,allocation_source_name=allocation_source_name)
    total_allocation = 0.0
    for data in user_allocation:
        total_allocation += data['applicable_duration']
    if burn_rate:
        burn_rate_total = 0 if len(user_allocation)<1 else user_allocation[-1]['burn_rate']
        return [round(total_allocation/3600.0,2),burn_rate_total]
    return round(total_allocation/3600.0,2)
