import numpy as np
from .plot_lfric_coords import get_lfric_coords_2d
from .extrusions import generate_extrusion

def extract_lfric_2D_data(data_file, field_name, time_idx,
                          extrusion_details=None, slice_name=None,
                          slice_idx=None, num_points=None, central_lon=0.0,
                          plot_coords_1d=None, testname=None):

    #--------------------------------------------------------------------------#
    # Checks
    #--------------------------------------------------------------------------#

    # TODO: fill in checks here

    if slice_name not in ['xy','yz','xz', None]:
        raise ValueError('For 2D plots slice must be xy, yz or xz')

    # Work out what time variable is called
    try:
        time = data_file.variables['time'][time_idx]
        lfric_initial = False
    except KeyError:
        try:
            time = data_file.variables['time_instant'][time_idx]
            lfric_initial = False
        except KeyError:
            # We have no time variable so this is the lfric_initial file
            time = 0
            lfric_initial = True

    #--------------------------------------------------------------------------#
    # Construct coordinate points
    #--------------------------------------------------------------------------#

    # Get dimension names
    if lfric_initial:
        if len(data_file.variables[field_name].dimensions) == 1:
            # 2D data
            vert_placement = None
            hori_placement = data_file.variables[field_name].dimensions[0][1:]
        else:
            vert_placement = data_file.variables[field_name].dimensions[0]
            # these will begin with "n" so slice to get rid of this
            hori_placement = data_file.variables[field_name].dimensions[1][1:]
    else:
        if len(data_file.variables[field_name].dimensions) == 2:
            # 2D data
            vert_placement = None
            hori_placement = data_file.variables[field_name].dimensions[1][1:]
        else:
            vert_placement = data_file.variables[field_name].dimensions[1]
            # these will begin with "n" so slice to get rid of this
            hori_placement = data_file.variables[field_name].dimensions[2][1:]

    plot_coords, data_coords, interp_coords_2d, \
    coord_labels, coord_lims, coord_ticks, \
    slice_label = get_lfric_coords_2d(data_file, hori_placement, vert_placement,
                                      slice_name, slice_idx, num_points=num_points,
                                      extrusion_details=extrusion_details,
                                      central_lon=central_lon,
                                      plot_coords_1d=plot_coords_1d)

    #--------------------------------------------------------------------------#
    # Interpolate field data
    #--------------------------------------------------------------------------#

    from scipy.interpolate import griddata

    field_data = np.zeros_like(plot_coords[0])
    if lfric_initial:
        if vert_placement is None:
            field_full = data_file.variables[field_name][:]
        else:
            field_full = data_file.variables[field_name][:,:]
    else:
        if vert_placement is None:
            field_full = data_file.variables[field_name][time_idx,:]
        else:
            field_full = data_file.variables[field_name][time_idx,:,:]

    if slice_name == 'xy':
        if vert_placement is None:
            # No slicing needed
            field_data = griddata(data_coords, field_full, interp_coords_2d, method='linear')
            field_near = griddata(data_coords, field_full, interp_coords_2d, method='nearest')
            field_data[np.isnan(field_data)] = field_near[np.isnan(field_data)]
        else:
            # Just do interpolation at that level
            field_data = griddata(data_coords, field_full[slice_idx], interp_coords_2d, method='linear')
            field_near = griddata(data_coords, field_full[slice_idx], interp_coords_2d, method='nearest')
            field_data[np.isnan(field_data)] = field_near[np.isnan(field_data)]

    else:
        # Need to loop through levels
        for level in range(np.shape(field_full)[0]):
            slice_data = griddata(data_coords, field_full[level], interp_coords_2d, method='linear')
            slice_near = griddata(data_coords, field_full[level], interp_coords_2d, method='nearest')
            slice_data[np.isnan(slice_data)] = slice_near[np.isnan(slice_data)]

            field_data[level] = slice_data

    if slice_name in ['xz', 'yz']:
        # Transform extrusion for plot coordinates, if required
        # Interpolation should have happened in eta-space
        vertical_coords_1d = generate_extrusion(extrusion_details, vert_placement,
                                                np.shape(plot_coords)[1])
        for row_idx in range(np.shape(plot_coords)[1]):
            plot_coords[1][row_idx][:] = vertical_coords_1d[row_idx]


    data_metadata = {'time': time, 'slice_label': slice_label,
                     'coord_labels': coord_labels, 'coord_lims': coord_lims,
                     'coord_ticks': coord_ticks}

    return plot_coords[0], plot_coords[1], field_data, data_metadata
