from __future__ import division
import os, argparse, uuid, time

import omero
import omero.model  # had to add this to prevent an error ---simleo
import omero_Tables_ice
import omero_SharedResources_ice

import numpy as np


TABLE_NAME = 'ometable_test.h5'
VID_SIZE = 34


def make_a_vid():
    return "V0%s" % uuid.uuid4().hex.upper()


def create_table(session, nrows, ncols):
    vids = omero.grid.StringColumn('vid', 'GDO VID', VID_SIZE)
    op_vids = omero.grid.StringColumn('op_vid', 'Last op VID', VID_SIZE)
    probs = omero.grid.FloatArrayColumn('probs', 'Probs', 2*ncols)
    confs = omero.grid.FloatArrayColumn('confidence', 'Confs', ncols)
    start = time.time()
    r = session.sharedResources()
    m = r.repositories()
    i = m.descriptions[0].id.val
    table = r.newTable(i, TABLE_NAME)
    table.initialize([vids, op_vids, probs, confs])
    #--
    for col in vids, op_vids:
        col.values = [make_a_vid() for _ in xrange(nrows)]
    probs.values = [np.random.random(2*ncols).astype(np.float32)
                    for _ in xrange(nrows)]
    confs.values = [np.random.random(ncols).astype(np.float32)
                    for _ in xrange(nrows)]
    table.addData([vids, op_vids, probs, confs])
    print "  table created in %.3f s" % (time.time() - start)
    return table


def open_table(session):
    qs = session.getQueryService()
    ofile = qs.findAllByString(
        'OriginalFile', 'name', TABLE_NAME, True, None
        )[0]  # first table with that name
    r = session.sharedResources()
    t = r.openTable(ofile)
    return t


def drop_table(session):
    qs = session.getQueryService()
    ofiles = qs.findAllByString(
        'OriginalFile', 'name', TABLE_NAME, True, None
        )  # *all* tables with that name, make sure we get a clean state
    us = session.getUpdateService()
    for of in ofiles:
        us.deleteObject(of)


def get_call_rate(table, threshold=0.05):
    nrows = table.getNumberOfRows()
    col_headers = [h.name for h in table.getHeaders()]
    conf_index = col_headers.index("confidence")
    start = time.time()
    data = table.read([conf_index], 0, nrows)
    print "  confidence data read in %.3f s" % (time.time() - start)
    start = time.time()    
    col = data.columns[0]
    s = sum(sum(x for x in row if x <= threshold) for row in col.values)
    call_rate = s / (nrows * col.size)
    print "  call rate computed in %.3f s" % (time.time() - start)
    return call_rate


def run_test(client, nrows, ncols):
    session = client.getSession()
    #--
    table = create_table(session, nrows, ncols)
    table.close()
    #--
    table = open_table(session)
    r = get_call_rate(table)
    table.close()
    drop_table(session)
    return r


def _run_on_server():
    import omero.scripts as scripts
    client = None
    try:
        client = scripts.client(
            "table_performance.py", "check table performance",
            scripts.Long("nrows").inout(),
            scripts.Long("ncols").inout(),
            scripts.Long("callrate").out(),
            )
        nrows = client.getInput("nrows")
        ncols = client.getInput("ncols")
        r = run_test(client, nrows, ncols)
        client.setOutput("callrate", r)
    finally:
        if client is not None:
            client.closeSession()


def _run_on_client():
    parser = argparse.ArgumentParser(description="test tables")
    parser.add_argument('--nrows', type=int, metavar="INT", default=100,
                        help="number of rows")
    parser.add_argument('--ncols', type=int, metavar="INT", default=10000,
                        help="number of columns")
    parser.add_argument('--clean', action="store_true",
                        help="don't run the test; clean up tables instead")
    args = parser.parse_args()
    #--
    ome_host = os.getenv('OME_HOST', 'localhost')
    ome_user = os.getenv('OME_USER', 'root')
    ome_passwd = os.getenv('OME_PASSWD', 'romeo')
    #--
    client = None
    print 'Connecting to %s' % ome_host
    try:
        client = omero.client(ome_host)
        session = client.createSession(ome_user, ome_passwd)
        if args.clean:
            print "cleaning up the mess"
            drop_table(session)
        else:
            r = run_test(client, args.nrows, args.ncols)
            print "callrate: %.3f" % r
    finally:
        if client is not None:
            client.closeSession()


if __name__ == '__main__':
    main = _run_on_client
    main()
