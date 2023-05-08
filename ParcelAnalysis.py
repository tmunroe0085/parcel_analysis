#******************************************************* 
# FILE: Parcel Analysis for Vacant Land
# AUTHOR: Thailynn Munroe
# EMAIL: thailynn.munroe@gmail.com
# MODIFIED BY: n/a
# ORGANIZATION: Little Sister Land Company 
# CREATION DATE: 05/08/2023
# LAST MOD DATE: (Optional, add when modified)
# PURPOSE: To add attribute information to vacant land parcels for better decision making
# DEPENDENCIES: n/a
#********************************************************

import os
import arcpy
from arcpy.sa import *
from sys import argv

parcels = arcpy.GetParameterAsText(0)
flood_zones = arcpy.GetParameterAsText(1)
wetlands = arcpy.GetParameterAsText(2)
roads = arcpy.GetParameterAsText(3)
slope_raster = arcpy.GetParameterAsText(4)
forest = arcpy.GetParameterAsText(5)
default_gdb = arcpy.GetParameterAsText(6)


def parcel_analysis(wetlands, flood_zones, roads, parcels, slope_raster, forest, default_gdb):

    arcpy.env.workspace = default_gdb
    arcpy.env.overwriteOutput = True

    # Calculate parcel acres
    arcpy.management.CalculateGeometryAttributes(parcels, [["GIS_ACRES", "AREA"]], area_unit="ACRES")
    arcpy.management.AlterField(parcels, "GIS_ACRES", new_field_alias="GIS Calculated Acres")

    # Buffer parcels
    parcel_buffer = os.path.join(default_gdb, "parcel_buffer")
    arcpy.analysis.Buffer(parcels, parcel_buffer, "1 MILE")
    print("Parcels buffered")

    # Buffer roads
    road_buffer = os.path.join(default_gdb, "roads_buffer")
    arcpy.analysis.Buffer(roads, road_buffer, "150 FEET")
    print("Roads buffered")

    # Clip slope
    slope_clip = os.path.join(default_gdb, "slope_clip")
    desc = arcpy.Describe(parcel_buffer)
    xmin = desc.extent.XMin
    xmax = desc.extent.XMax
    ymin = desc.extent.YMin
    ymax = desc.extent.YMax
    rectangle = f"{xmin} {ymin} {xmax} {ymax}"
    arcpy.management.Clip(slope_raster, rectangle, slope_clip, in_template_dataset=parcel_buffer,
                          clipping_geometry="ClippingGeometry")
    print("Slope clipped")

    # Project slope
    sr = desc.spatialReference
    slope_clip_project = os.path.join(default_gdb, "slope_clip_project")
    arcpy.management.ProjectRaster(slope_clip, slope_clip_project, sr)
    print("Slope projected")

    # Reclassify slope
    slope_clip_project_reclass = os.path.join(default_gdb, "slope_clip_project_reclass")
    remap = RemapRange([[0,30,1],[30.1,100,"NODATA"],])
    slope_clip_reclass = Reclassify(slope_clip_project, "Value", remap)
    slope_clip_reclass.save(slope_clip_project_reclass)
    print("Slope reclassified")

    # Convert slope to polygon
    slope_polygon = os.path.join(default_gdb, "slope_polygon")
    arcpy.conversion.RasterToPolygon(slope_clip_project_reclass, slope_polygon, "NO_SIMPLIFY", "Value")
    print("Slope converted to polygon")

    # Summarize within slope
    parcel_slope = os.path.join(default_gdb, "parcel_slope")
    arcpy.analysis.SummarizeWithin(parcels, slope_polygon, parcel_slope, sum_shape="ADD_SHAPE_SUM", shape_unit="ACRES")
    arcpy.management.AlterField(parcel_slope, "sum_Area_ACRES", "SLOPE_ACRES", new_field_alias="Slope Acres")
    arcpy.management.DeleteField(parcel_slope, "Polygon_Count")
    arcpy.management.AddField(parcel_slope, "SLOPE_PERCENT", "FLOAT", field_alias="Slope Percent")
    expression_flood_zones = "!SLOPE_ACRES!/!GIS_ACRES!"
    arcpy.management.CalculateField(parcel_slope, "SLOPE_PERCENT", expression_flood_zones)

    # Summarize within roads
    parcel_roads = os.path.join(default_gdb, "parcel_roads")
    arcpy.analysis.SummarizeWithin(parcel_slope, road_buffer, parcel_roads, sum_shape="ADD_SHAPE_SUM",
                                   shape_unit="ACRES")
    arcpy.management.AddField(parcel_roads, "ROAD_WITHIN_150FT", "TEXT", field_alias="Road Within 150ft")
    expression_roads = "roads(!Polygon_Count!)"
    code_block = """def roads(poly_count):
        if poly_count > 0:
            return 'yes' 
        else:
            return 'no'"""
    arcpy.management.CalculateField(parcel_roads, "ROAD_WITHIN_150FT", expression_roads,  "PYTHON3", code_block)
    arcpy.management.DeleteField(parcel_roads, "Polygon_Count")
    arcpy.management.DeleteField(parcel_roads, "sum_Area_ACRES")

    # Summarize within flood zones
    parcel_flood_zones = os.path.join(default_gdb, "parcel_flood_zones")
    arcpy.analysis.SummarizeWithin(parcel_roads, flood_zones, parcel_flood_zones, sum_shape="ADD_SHAPE_SUM",
                                   shape_unit="ACRES")
    arcpy.management.AlterField(parcel_flood_zones, "sum_Area_ACRES", "FLOOD_ZONE_ACRES",
                                new_field_alias="Flood Zone Acres")
    arcpy.management.AddField(parcel_flood_zones, "FLOOD_ZONE_PERCENT", "FLOAT", field_alias="Flood Zone Percent")
    expression_flood_zones = "!FLOOD_ZONE_ACRES!/!GIS_ACRES!"
    arcpy.management.CalculateField(parcel_flood_zones, "FLOOD_ZONE_PERCENT", expression_flood_zones)
    arcpy.management.DeleteField(parcel_flood_zones, "Polygon_Count")

    # Summarize within wetlands
    parcel_wetlands = os.path.join(default_gdb, "parcel_wetlands")
    arcpy.analysis.SummarizeWithin(parcel_flood_zones, wetlands, parcel_wetlands, sum_shape="ADD_SHAPE_SUM",
                                   shape_unit="ACRES")
    arcpy.management.AlterField(parcel_wetlands, "sum_Area_ACRES", "WETLANDS_ACRES", new_field_alias="Wetlands Acres")
    arcpy.management.AddField(parcel_wetlands, "WETLANDS_PERCENT", "FLOAT", field_alias="Wetlands Percent")
    expression_wetlands = "!WETLANDS_ACRES!/!GIS_ACRES!"
    arcpy.management.CalculateField(parcel_wetlands, "WETLANDS_PERCENT", expression_wetlands)
    arcpy.management.DeleteField(parcel_wetlands, "Polygon_Count")


    # Clip forests
    forest_clip = os.path.join(default_gdb, "forest_clip")
    desc = arcpy.Describe(parcel_buffer)
    xmin = desc.extent.XMin
    xmax = desc.extent.XMax
    ymin = desc.extent.YMin
    ymax = desc.extent.YMax
    rectangle = f"{xmin} {ymin} {xmax} {ymax}"
    arcpy.management.Clip(forest, rectangle, forest_clip, in_template_dataset=parcel_buffer,
                          clipping_geometry="ClippingGeometry")
    print("Forest clipped")

    # Project forests
    sr = desc.spatialReference
    forest_clip_project = os.path.join(default_gdb, "forest_clip_project")
    arcpy.management.ProjectRaster(forest_clip, forest_clip_project, sr)
    print("Slope projected")

    # Reclassify slope
    forest_clip_project_reclass = os.path.join(default_gdb, "forest_clip_project_reclass")
    remap = RemapRange([[40, 44, 1], [0, 39, "NODATA"],  [45, 100, "NODATA"]])
    forest_clip_reclass = Reclassify(forest_clip_project, "Value", remap)
    forest_clip_reclass.save(forest_clip_project_reclass)
    print("Slope reclassified")

    # Convert slope to polygon
    forest_polygon = os.path.join(default_gdb, "forest_polygon")
    arcpy.conversion.RasterToPolygon(forest_clip_project_reclass, forest_polygon, "NO_SIMPLIFY", "Value")
    print("Slope converted to polygon")

    # Summarize within forests
    parcel_forest = os.path.join(default_gdb, "parcel_analysis_final")
    arcpy.analysis.SummarizeWithin(parcel_wetlands, forest_polygon, parcel_forest, sum_shape="ADD_SHAPE_SUM",
                                   shape_unit="ACRES")
    arcpy.management.AlterField(parcel_forest, "sum_Area_ACRES", "FOREST_ACRES", new_field_alias="Forest Acres")
    arcpy.management.AddField(parcel_forest, "FOREST_PERCENT", "FLOAT", field_alias="Forest Percent")
    expression_forest = "!FOREST_ACRES!/!GIS_ACRES!"
    arcpy.management.CalculateField(parcel_forest, "FOREST_PERCENT", expression_forest)
    arcpy.management.DeleteField(parcel_forest, "Polygon_Count")

    return


if __name__ == "__main__":
    parcel_analysis(wetlands, flood_zones, roads, parcels, slope_raster, forest, default_gdb)
