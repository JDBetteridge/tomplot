"""
Routines for extracting data from Gusto and LFRic field data files.
"""

import numpy as np
import pandas as pd
import warnings
from .cubed_sphere import lonlat_to_alphabeta

__all__ = ["extract_gusto_field", "extract_gusto_coords",
           "extract_lfric_field", "extract_lfric_coords",
           "extract_lfric_heights", "extract_lfric_vertical_slice"]


def extract_gusto_field(dataset, field_name, time_idx=None, level=None):
    """
    Extracts the data corresponding to a Gusto field.

    Args:
        dataset (:class:`Dataset`): the netCDF dataset containing the data.
        field_name (str): the name of the field to be extracted.
        time_idx (int, optional): index of the time point to extract at.
            Defaults to None, in which case all time points are extracted.
        level (int, optional): index of the vertical level to extract at (if
            there is any). Defaults to None, in which case all of the data is
            extracted.
    """

    # If time_idx or level are None, we would index array as :
    # Make equivalent slice objects to these to simplify code below
    if time_idx is None:
        time_idx = slice(None, None)
    if level is None:
        level = slice(None, None)

    # Work out the data structure based on the domain metadata
    domain = dataset.variables['domain_type'][:]

    if domain == 'spherical_shell':
        field_data = dataset[field_name]['field_values'][:,time_idx]
    else:
        raise NotImplementedError(f'extract_gusto_field: domain {domain} '
                                  +' either not implemented or recognised')
    return field_data


def extract_gusto_coords(dataset, field_name, slice_along=None):
    """
    Extracts the arrays of coordinate data for a specified field from a Gusto
    field data file.

    Args:
        dataset (:class:`Dataset`): the netCDF dataset containing the data.
        field_name (str): the name of the field to be extracted.
        slice_along (str, optional): a string specifying which direction to
            slice 3D data, and hence which coordinates are to be returned.
            Defaults to None.

    Returns:
        tuple of `numpy.ndarray`s: the coordinate data.
    """

    coord_variable = dataset[field_name]['field_values'].dimensions[0]
    # Variable name is "coords_*". We want to find the suffix
    coord_space = coord_variable[7:]

    # Work out which coordinates to expect based on the domain metadata
    domain = dataset.variables['domain_type'][:]
    if domain == 'spherical_shell':
        coords_X = dataset.variables[f'lon_{coord_space}'][:]
        coords_Y = dataset.variables[f'lat_{coord_space}'][:]
        return coords_X, coords_Y
    else:
        raise NotImplementedError(f'extract_gusto_coords: domain {domain} '
                                  +' either not implemented or recognised')


def extract_lfric_field(dataset, field_name, time_idx=None, level=None):
    """
    Extracts the data corresponding to a LFRic field.

    Args:
        dataset (:class:`Dataset`): the netCDF dataset containing the data.
        field_name (str): the name of the field to be extracted.
        time_idx (int, optional): index of the time point to extract at.
            Defaults to None, in which case all time points are extracted.
        level (int, optional): index of the vertical level to extract at (if
            there is any). Defaults to None, in which case all of the data is
            extracted.
    """

    # If time_idx or level are None, we would index array as : and extract the
    # whole field - make equivalent slice objects to this to simplify code below
    if time_idx is None:
        time_idx = slice(None, None)
    if level is None:
        level = slice(None, None)

    # 3D data
    if len(dataset[field_name].dimensions) == 3:
        field_data = dataset[field_name][time_idx,level,:]

    # 2D time-varying field
    elif (len(dataset[field_name].dimensions) == 2
          and dataset[field_name].dimensions[0] == 'time'):
        field_data = dataset[field_name][time_idx,:]

    # 3D non-time-varying field
    elif len(dataset[field_name].dimensions) == 2:
        field_data = dataset[field_name][level,:]

    # 2D non-time-varying field
    elif len(dataset[field_name].dimensions) == 1:
        field_data = field_data = dataset[field_name][:]

    else:
        raise RuntimeError(
            'extract_lfric_field: unable to work out how to handle data with '
            + f'{len(dataset[field_name].dimensions.shape)} dimensions')

    return field_data


def extract_lfric_coords(dataset, field_name):
    """
    Extracts the arrays of coordinate data for a specified field from an LFRic
    field data file.

    Args:
        dataset (:class:`Dataset`): the netCDF dataset containing the data.
        field_name (str): the name of the field to be plotted.

    Returns:
        tuple of `numpy.ndarray`s: the coordinate data.
    """

    # Get name of coordinate data, e.g. "nMesh2d_edge"
    root_coords_name = dataset[field_name].dimensions[-1]
    # Corresponding variable name is "Mesh2d_edge_x"
    coords_X_name = root_coords_name[1:]+'_x'
    coords_Y_name = root_coords_name[1:]+'_y'

    coords_X = dataset[coords_X_name][:]
    coords_Y = dataset[coords_Y_name][:]

    return coords_X, coords_Y


def extract_lfric_heights(height_dataset, field_dataset, field_name, level=None):
    """
    Extracts the arrays of height data for a specified field from an LFRic
    data file.

    Args:
        height_dataset (:class:`Dataset`): the netCDF dataset containing the
            height data to be extracted.
        field_dataset (:class:`Dataset`): the netCDF dataset containing the
            data of the field to be plotted.
        field_name (str): the name of the field to be plotted.
        level (int, optional): the vertical level to extract the heights at.
            Defaults to None, in which case the whole height field is extracted.

    Returns:
        `numpy.ndarray`: the height data.
    """

    # Work out which level this should be on
    if (field_dataset[field_name].dimensions[1] == 'half_levels'
        and field_dataset[field_name].dimensions[2] == 'nMesh2d_face'):
        height_name = 'height_w3'
    elif (field_dataset[field_name].dimensions[1] == 'full_levels'
          and field_dataset[field_name].dimensions[2] == 'nMesh2d_face'):
        height_name = 'height_wth'
    else:
        raise NotImplementedError(f'Dimensions for {field_name} are not '
            + 'implemented so cannot work out height field')

    # If time_idx or level are None, we would index array as : and extract the
    # whole field - make equivalent slice objects to this to simplify code below
    if level is None:
        level = slice(None, None)

    # Data may be time-varying or not, so these cases need handling separately
    if len(height_dataset[height_name].dimensions) == 2:
        # Initial data with no time value
        heights = height_dataset[height_name][level,:]
    elif len(height_dataset[height_name].dimensions) == 3:
        # 3D data -- take the first time value
        heights = height_dataset[height_name][0,level,:]
    else:
        raise RuntimeError(f'Trying to extract {height_name} field, but '
                            + 'the array is not 2D or 3D, so cannot proceed')

    return heights


def extract_lfric_vertical_slice(field_dataset, field_name, time_idx,
                                 slice_along, slice_at=0.0, height_dataset=None,
                                 levels=None, panel=None, tolerance=1e-4):
    """
    Extracts the field and coordinates for a vertical slice of LFRic data.

    Args:
        field_dataset (:class:`Dataset`): the netCDF dataset containing the
            data of the field to be extracted.
        field_name (str): the name of the field to be extracted.
        time_idx (int): the time index at which to extract the data. Can be None
            if not relevant.
        slice_along (str): _description_
        slice_at (float, optional): the coordinate value at which to slice the
            data. Defaults to 0.0.
        height_dataset (:class:`Dataset`, optional): the netCDF dataset
            containing the height data to be extracted. If not specified, model
            level is used instead as a vertical coordinate. Defaults to None.
        levels (iter, optional): iterable of integers, indicating which model
            levels to extract the slice at. Defaults to None, in which case data
            is extracted at all levels.
        panel (int, optional): if "alpha" or "beta" are specified as the coord
            to slice along, then this argument must also be provided, in order
            to indicate which panel to slice along. Defaults to None.
        tolerance (float, optional): tolerance to use in determining how close
            data points are to the points to slice along. Defaults to 1e-4.
    """

    assert slice_along in ['x', 'y', 'lon', 'lat', 'alpha', 'beta'], \
        f'slice_along variable must correspond to a coordinate. {slice_along}' \
        + ' is not a valid value'

    if slice_along in ['alpha', 'beta']:
        assert panel is not None, 'extract_lfric_vertical_slice: if slicing ' \
            + 'along alpha or beta coordinates, panel argument must be provided'

    # Combine coord systems into general X/Y system to simplify later code
    if slice_along in ['x', 'lon', 'alpha']:
        local_slice_along = 'X'
    if slice_along in ['y', 'lat', 'beta']:
        local_slice_along = 'Y'
    local_X_coord = 'Y' if local_slice_along == 'X' else 'X'

    # ------------------------------------------------------------------------ #
    # Determine number of vertical levels for this field
    # ------------------------------------------------------------------------ #
    if levels is None:
        if (len(field_dataset[field_name].dimensions) == 2):
            num_levels = np.shape(field_dataset[field_name])[0]
        elif (len(field_dataset[field_name].dimensions) == 3):
            num_levels = np.shape(field_dataset[field_name])[1]
        else:
            raise RuntimeError('extract_lfric_vertical_slice: cannot work with'
                               + 'data of this shape')

        levels = range(num_levels)
    else:
        num_levels = len(levels)

    # ------------------------------------------------------------------------ #
    # Extract horizontal coordinates for this field
    # ------------------------------------------------------------------------ #
    coords_X, coords_Y = extract_lfric_coords(field_dataset, field_name)
    # Convert to alpha/beta if that is specified
    if slice_along in ['alpha', 'beta']:
        # Assume coords are already lon/lat
        coords_X, coords_Y, panel_ids = lonlat_to_alphabeta(coords_X, coords_Y)

    # ------------------------------------------------------------------------ #
    # Loop through levels and build up data
    # ------------------------------------------------------------------------ #
    for lev_idx, level in enumerate(levels):
        # Extract field data for this level
        field_data_level = extract_lfric_field(field_dataset, field_name,
                                               time_idx=time_idx, level=level)

        # Make dictionary of data, to pass to pandas DataFrame
        data_dict = {'field_data': field_data_level,
                     'X': coords_X, 'Y': coords_Y}

        # Add height data, if specified
        if height_dataset is not None:
            height_data_level = extract_lfric_heights(
                height_dataset, field_dataset, field_name, level)
            data_dict['height'] = height_data_level

        # Add panel IDs, if necessary
        if slice_along in ['alpha', 'beta']:
            data_dict['panel'] = panel_ids

        # -------------------------------------------------------------------- #
        # Make data frame and filter it
        # -------------------------------------------------------------------- #
        df = pd.DataFrame(data_dict)

        # Are there values close to the specified "slice_at" value?
        slice_df = df[np.abs(df[local_slice_along] - slice_at) < tolerance]
        # Additionally filter based on panel
        if slice_along in ['alpha', 'beta']:
            slice_df = slice_df[slice_df['panel'] == panel]

        if len(slice_df) == 0:
            # If there aren't points, we shall take nearest two sets of points
            warnings.warn('extract_lfric_vertical_slice: No data points found '
                          + f'at {slice_along} = {slice_at}. Finding nearest '
                          + 'points instead. This implies that you will need to'
                          + 'regrid')
            raise NotImplementedError

        # -------------------------------------------------------------------- #
        # Add data to a larger array
        # -------------------------------------------------------------------- #
        # Create data arrays if we're doing the first level
        if lev_idx == 0:
            len_data = len(slice_df['field_data'].values)
            field_data = np.zeros((len_data, num_levels))
            coords_X_final = np.zeros((len_data, num_levels))
            coords_Y_final = np.zeros((len_data, num_levels))
            coords_Z_final = np.zeros((len_data, num_levels))

        # Populate data arrays
        field_data[:,lev_idx] = slice_df['field_data'].values
        coords_X_final[:,lev_idx] = slice_df[local_X_coord].values
        coords_Y_final[:,lev_idx] = slice_df[local_slice_along].values
        coords_Z_final[:,lev_idx] = level if height_dataset is None else slice_df['height'].values

    return field_data, coords_X_final, coords_Y_final, coords_Z_final
