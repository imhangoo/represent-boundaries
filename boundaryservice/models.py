import re

from django.contrib.gis.db import models
from django.core import urlresolvers
from django.template.defaultfilters import slugify

from appconf import AppConf

from boundaryservice.fields import ListField, JSONField
from boundaryservice.utils import get_site_url_root

class MyAppConf(AppConf):
    MAX_GEO_LIST_RESULTS = 80 # In a /boundary/shape query, if more than this
                        # number of resources are matched, throw an error

app_settings = MyAppConf()

class BoundarySet(models.Model):
    """
    A set of related boundaries, such as all Wards or Neighborhoods.
    """
    slug = models.SlugField(max_length=200, primary_key=True, editable=False)

    name = models.CharField(max_length=100, unique=True,
        help_text='Category of boundaries, e.g. "Community Areas".')
    singular = models.CharField(max_length=100,
        help_text='Name of a single boundary, e.g. "Community Area".')
    kind_first = models.BooleanField(
        help_text='If true, boundary display names will be "<kind> <name>" (e.g. Austin Community Area), otherwise "<name> <kind>" (e.g. 43rd Precinct).')
    authority = models.CharField(max_length=256,
        help_text='The entity responsible for this data\'s accuracy, e.g. "City of Chicago".')
    domain = models.CharField(max_length=256,
        help_text='The area that this BoundarySet covers, e.g. "Chicago" or "Illinois".')
    hierarchy = models.CharField(max_length=2, blank=True,
        choices=( ('F', 'Federal'),
                  ('P', 'Provincial'),
                  ('M', 'Municipal'),
                  ('O', 'Other')))
    last_updated = models.DateField(
        help_text='The last time this data was updated from its authority (but not necessarily the date it is current as of).')
    href = models.URLField(blank=True,
        help_text='The url this data was found at, if any.')
    notes = models.TextField(blank=True,
        help_text='Notes about loading this data, including any transformations that were applied to it.')
    count = models.IntegerField(
        help_text='Total number of features in this boundary set.')
    metadata_fields = ListField(separator='|', blank=True,
        help_text='What, if any, metadata fields were loaded from the original dataset.')

    class Meta:
        ordering = ('name',)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        return super(BoundarySet, self).save(*args, **kwargs)

    def __unicode__(self):
        return self.name

    def as_dict(self):
        r = {
            'boundaries_url': urlresolvers.reverse('boundaryservice_boundary_list', kwargs={'set_slug': self.slug}),
        }
        for f in ('name', 'singular', 'authority', 'domain', 'href', 'notes', 'count', 'metadata_fields'):
            r[f] = getattr(self, f)
        return r

    @staticmethod
    def get_dicts(sets):
        return [
            {
                'url': urlresolvers.reverse('boundaryservice_set_detail', kwargs={'slug': s.slug}),
                'boundaries_url': urlresolvers.reverse('boundaryservice_boundary_list', kwargs={'set_slug': s.slug}),
                'boundaries_count': s.count,
                'name': s.name,
                'domain': s.domain,
                'hierarchy': s.get_hierarchy_display(),
            } for s in sets
        ]

class Boundary(models.Model):
    """
    A boundary object, such as a Ward or Neighborhood.
    """
    set = models.ForeignKey(BoundarySet, related_name='boundaries',
        help_text='Category of boundaries that this boundary belongs, e.g. "Community Areas".')
    set_name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=200, db_index=True)
    external_id = models.CharField(max_length=64,
        help_text='The boundaries\' unique id in the source dataset, or a generated one.')
    name = models.CharField(max_length=192, db_index=True,
        help_text='The name of this boundary, e.g. "Austin".')
    display_name = models.CharField(max_length=256,
        help_text='The name and kind of the field to be used for display purposes.')
    metadata = JSONField(blank=True,
        help_text='The complete contents of the attribute table for this boundary from the source shapefile, structured as json.')
    shape = models.MultiPolygonField(
        help_text='The geometry of this boundary in EPSG:4326 projection.')
    simple_shape = models.MultiPolygonField(
        help_text='The geometry of this boundary in EPSG:4326 projection and simplified to 0.0001 tolerance.')
    centroid = models.PointField(
        null=True,
        help_text='The centroid (weighted center) of this boundary in EPSG:4326 projection.')
    
    objects = models.GeoManager()

    class Meta:
        unique_together = (('slug', 'set'))

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        return super(Boundary, self).save(*args, **kwargs)

    def __unicode__(self):
        return self.display_name

    def as_dict(self):
        return {
            'set_url': urlresolvers.reverse('boundaryservice_set_detail', kwargs={'slug': self.set_id}),
            'set_name': self.set_name,
            'name': self.name,
            'display_name': self.display_name,
            'metadata': self.metadata,
            'external_id': self.external_id,
        }

    @staticmethod
    def prepare_queryset_for_get_dicts(qs):
        return qs.values_list('slug', 'set', 'name', 'display_name', 'set_name')

    @staticmethod
    def get_dicts(boundaries):
        return [
            {
                'url': urlresolvers.reverse('boundaryservice_boundary_detail', kwargs={'slug': b[0], 'set_slug': b[1]}),
                'name': b[2],
                'display_name': b[3],
                'set_url': urlresolvers.reverse('boundaryservice_set_detail', kwargs={'slug': b[1]}),
                'set_name': b[4],
            } for b in boundaries
        ]

